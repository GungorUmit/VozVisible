import os
import sys
import subprocess
import sqlite3
import time
import glob
import csv
from celery import Celery

# Ensure root dir is in sys.path so celery can import 'services'
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

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

# ── Cargar vocabulario real del diccionario LSE ──────────────────
# Esto se lee UNA vez al arrancar el worker. Así sabemos exactamente
# qué palabras puede generar el motor de vídeo.
LEXICON_VOCAB = set()
_index_path = os.path.join(ROOT_DIR, 'spoken_to_signed', 'assets', 'lse_lexicon', 'index.csv')
try:
    with open(_index_path, encoding='utf-8') as _f:
        for _row in csv.DictReader(_f):
            word = (_row.get('words') or '').strip().lower()
            if word:
                LEXICON_VOCAB.add(word)
    print(f"[Celery] Vocabulario LSE cargado: {len(LEXICON_VOCAB)} palabras.")
except Exception as _e:
    print(f"[Celery] AVISO: No se pudo cargar vocabulario LSE: {_e}")


def _filter_glosses(glosses_str):
    """Filtra las glosas del LLM y devuelve SOLO las que existen en el diccionario."""
    words = glosses_str.lower().split()
    valid = [w for w in words if w in LEXICON_VOCAB]
    print(f"[Celery] Filtro de glosas: entrada={words} -> validas={valid}")
    return " ".join(valid)


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

    # Por defecto: usar lse_rules (siempre funciona)
    cmd = [sys.executable, "generate_video.py", "--text", texto, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]

    # Intentar usar el pipeline multi-agente si hay clave de Groq
    if groq_key:
        try:
            from services.agents.orchestrator import run_multi_agent_pipeline
            print(f"[Celery] Iniciando pipeline multi-agente para: {texto}")

            def log_cb(msg_dict):
                agent_logs.append(msg_dict)
                self.update_state(state='PROGRESS', meta={'logs': list(agent_logs)})

            agent_results = run_multi_agent_pipeline(texto, groq_key, log_callback=log_cb)

            clean_text = agent_results["clean_text"]
            glosses_raw = agent_results["glosses"]
            speed = agent_results["speed"]

            texto = clean_text

            # ── FILTRO DE SEGURIDAD ──────────────────────────────────
            # Filtramos las glosas del LLM contra el vocabulario REAL.
            # Si el LLM invento palabras que no existen -> las eliminamos.
            # Si no queda NINGUNA palabra valida -> usamos lse_rules.
            if glosses_raw:
                filtered_glosses = _filter_glosses(glosses_raw)

                if filtered_glosses:
                    # Hay palabras validas -> usar las glosas filtradas
                    print(f"[Celery] Usando glosas filtradas: {filtered_glosses}")
                    cmd = [
                        sys.executable, "generate_video.py",
                        "--text", clean_text,
                        "--output", output_path,
                        "--disable-fingerspelling",
                        "--precomputed-glosses", filtered_glosses
                    ]
                else:
                    # El LLM no genero nada util -> fallback a lse_rules
                    print(f"[Celery] AVISO: Ninguna glosa del LLM esta en el diccionario. Usando lse_rules.")
                    cmd = [sys.executable, "generate_video.py", "--text", clean_text, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]
            else:
                # No hubo glosas -> fallback a lse_rules
                cmd = [sys.executable, "generate_video.py", "--text", clean_text, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]

        except Exception as e:
            print(f"[Celery] Error en pipeline multi-agente: {e}. Usando lse_rules.")
            cmd = [sys.executable, "generate_video.py", "--text", texto, "--output", output_path, "--glosser", "lse_rules", "--disable-fingerspelling"]
    else:
        print("[Celery] No GROQ_API_KEY. Usando lse_rules por defecto.")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env, timeout=120)
        if os.path.exists(output_path):
            log_emission(texto, output_path)
            return {"status": "completed", "video_url": f"/{output_path}", "texto": texto, "logs": agent_logs}
        else:
            return {"status": "failed", "error": "No se pudo generar el video.", "logs": agent_logs}
    except subprocess.CalledProcessError as e:
        # Si INCLUSO lse_rules falla, dar un error claro con el detalle
        stderr_text = (e.stderr or "")[:500]
        print(f"[Celery] Error de generate_video.py: {stderr_text}")
        return {"status": "failed", "error": f"Error en la generacion del video: {stderr_text}", "logs": agent_logs}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Tiempo de generacion excedido.", "logs": agent_logs}
    except Exception as e:
        return {"status": "failed", "error": str(e), "logs": agent_logs}
