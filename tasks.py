import os
import sys
import subprocess
import sqlite3
import time
import glob
from celery import Celery

# Ensure root dir is in sys.path so celery can import 'services'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

celery_app = Celery(
    'vozvisible_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery CLI expects a variable named `celery` or `app` by default — provide alias
celery = celery_app

# Schedule: run cleanup every 12 hours
celery_app.conf.beat_schedule = {
    'cleanup-old-outputs-every-12-hours': {
        'task': 'tasks.cleanup_old_outputs',
        'schedule': 12 * 3600,
    },
}
celery_app.conf.timezone = 'UTC'

def log_emission(texto, output_path):
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute("INSERT INTO emissions (text, output_path) VALUES (?, ?)", (texto, output_path))
    conn.commit()
    conn.close()


@celery_app.task
def cleanup_old_outputs():
    """Delete mp4 files older than 24 hours from assets/output."""
    deleted = 0
    try:
        os.makedirs('assets/output', exist_ok=True)
        files = glob.glob('assets/output/*.mp4')
        now = time.time()
        for f in files:
            try:
                if os.path.getmtime(f) < now - (24 * 3600):
                    os.remove(f)
                    deleted += 1
            except Exception:
                continue
    except Exception:
        pass
    return {'deleted': deleted}

@celery_app.task(bind=True)
def async_generate_video(self, texto, slug, env):
    output_path = f"assets/output/{slug}.mp4"
    os.makedirs("assets/output", exist_ok=True)
    
    if os.path.exists(output_path):
        log_emission(texto, output_path)
        return {"status": "completed", "video_url": f"/{output_path}", "texto": texto, "cached": True}

    env = env or {}
    groq_key = env.get("GROQ_API_KEY")
    agent_logs = []
    
    # 1. Orquestación Multi-Agente
    if groq_key:
        try:
            from services.agents.orchestrator import run_multi_agent_pipeline
            print(f"[Celery] Iniciando pipeline multi-agente para: {texto}")
            
            # Callback para emitir logs de los agentes en tiempo real al frontend
            def log_cb(msg_dict):
                agent_logs.append(msg_dict)
                self.update_state(state='PROGRESS', meta={'logs': list(agent_logs)})
                
            agent_results = run_multi_agent_pipeline(texto, groq_key, log_callback=log_cb)
            
            clean_text = agent_results["clean_text"]
            glosses = agent_results["glosses"]
            speed = agent_results["speed"]
            
            # Reemplazar texto bruto por texto limpio para el log de SQLite
            texto = clean_text
            
            # Disable fingerspelling fallback so missing words are skipped but shown in subtitles
            cmd = [
                sys.executable, "generate_video.py", 
                "--text", clean_text, 
                "--output", output_path, 
                "--disable-fingerspelling"
            ]
            
            # Pasar glosas calculadas si el bucle del crítico tuvo éxito
            if glosses:
                cmd.extend(["--precomputed-glosses", glosses])
            else:
                cmd.extend(["--glosser", "lse_rules"])
                
        except ImportError as e:
            print(f"[Celery] Error cargando agentes: {e}. Usando fallback.")
            cmd = [sys.executable, "generate_video.py", "--text", texto, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]
    else:
        print("[Celery] No GROQ_API_KEY. Usando lse_rules por defecto.")
        cmd = [sys.executable, "generate_video.py", "--text", texto, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env, timeout=120)
        if os.path.exists(output_path):
            log_emission(texto, output_path)
            return {"status": "completed", "video_url": f"/{output_path}", "texto": texto, "logs": agent_logs}
        else:
            return {"status": "failed", "error": "No se pudo generar el video.", "logs": agent_logs}
    except subprocess.CalledProcessError as e:
        error_msg = "Error desconocido de generación."
        if "No poses found" in e.stderr or "not found" in e.stderr:
            error_msg = "Vocabulario insuficiente: algunas palabras no están en la base de datos LSE."
        elif "Exception:" in e.stderr:
            error_msg = "El motor de vídeo LSE abortó la generación (posible falta de recursos o diccionarios)."
        return {"status": "failed", "error": error_msg, "logs": agent_logs}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Tiempo de generación excedido.", "logs": agent_logs}
    except Exception as e:
        return {"status": "failed", "error": str(e), "logs": agent_logs}
