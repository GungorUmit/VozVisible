import os
import sys
import subprocess
import sqlite3
import time
import glob
import logging
from celery import Celery

celery_app = Celery(
    'vozvisible_tasks',
    broker='redis://localhost:6379/1',
    backend='redis://localhost:6379/1'
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
    # Use backend_improvements.py (The "AI Mind") for processing
    cmd = [sys.executable, "backend_improvements.py", "--text", texto, "--output", output_path]

    # Configure logging for the task
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("async_generate_video")

    # Allow longer timeout for complex AI + rendering runs (configurable via env)
    timeout_seconds = int(os.environ.get("AI_GENERATION_TIMEOUT", "900"))

    logger.info(f"Starting generation for slug={slug} timeout={timeout_seconds}s")
    try:
        # Update task state so callers can see progress
        try:
            self.update_state(state='PROGRESS', meta={'stage': 'starting', 'slug': slug})
        except Exception:
            pass

        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env, timeout=timeout_seconds)

        logger.info(f"Subprocess finished returncode={result.returncode}")
        if result.stdout:
            logger.info(f"Subprocess stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"Subprocess stderr: {result.stderr}")

        if os.path.exists(output_path):
            log_emission(texto, output_path)
            try:
                self.update_state(state='PROGRESS', meta={'stage': 'completed', 'video': output_path})
            except Exception:
                pass
            return {"status": "completed", "video_url": f"/{output_path}", "texto": texto}
        else:
            logger.error("Video file not found after subprocess completion")
            return {"status": "failed", "error": "No se pudo generar el video tras el proceso de IA."}
    except subprocess.CalledProcessError as e:
        stderr = e.stderr if hasattr(e, 'stderr') else str(e)
        logger.error(f"CalledProcessError: {stderr}")
        error_msg = f"Error en generación (IA): {stderr}"
        if "No poses found" in stderr or "Exception: No poses" in stderr:
            error_msg = "Vocabulario insuficiente: incluso tras la IA, algunas palabras no pudieron ser representadas."
        return {"status": "failed", "error": error_msg}
    except subprocess.TimeoutExpired as e:
        logger.error(f"TimeoutExpired after {timeout_seconds}s: {e}")
        return {"status": "failed", "error": "Tiempo de generación excedido (la IA tardó demasiado)."}
