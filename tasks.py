import os
import sys
import subprocess
import sqlite3
import time
import glob
import logging
import resource
import base64
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


def _log_rss(logger, prefix):
    try:
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        logger.info(f"{prefix} rss_kb={rss_kb}")
    except Exception:
        pass


def _store_video_artifact(job_id: str, output_path: str, ttl_seconds: int = 86400) -> None:
    """Persist the rendered MP4 so the web dyno can serve it even if the worker
    runs on a different instance.

    Uses Redis when available; otherwise it falls back silently to the filesystem.
    """
    try:
        import redis
    except Exception:
        return

    try:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        client = redis.Redis.from_url(redis_url)
        with open(output_path, "rb") as f:
            client.setex(f"vozvisible:video:{job_id}", ttl_seconds, f.read())
    except Exception:
        return


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
    # Bump this version whenever the rendering pipeline changes so old cached
    # videos do not keep being reused in the UI.
    pipeline_version = "v3"
    output_path = f"assets/output/{slug}_{pipeline_version}.mp4"
    os.makedirs("assets/output", exist_ok=True)
    
    if os.path.exists(output_path):
        log_emission(texto, output_path)
        _store_video_artifact(self.request.id, output_path)
        return {"status": "completed", "video_url": f"/api/video/{self.request.id}.mp4", "texto": texto, "cached": True}
    # Use backend_improvements.py (The "AI Mind") for processing
    cmd = [sys.executable, "backend_improvements.py", "--text", texto, "--output", output_path]

    # Configure logging for the task
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("async_generate_video")

    # Per-task logfile so we can fetch logs after the job finishes/crashes
    os.makedirs('assets/logs', exist_ok=True)
    task_log_path = f"assets/logs/{self.request.id}.log" if hasattr(self, 'request') else None
    task_log_f = None
    if task_log_path:
        try:
            task_log_f = open(task_log_path, 'a', encoding='utf-8')
            task_log_f.write(f"Starting task {self.request.id} for slug={slug}\n")
            task_log_f.flush()
        except Exception:
            task_log_f = None

    # Allow longer timeout for complex AI + rendering runs (configurable via env)
    timeout_seconds = int(os.environ.get("AI_GENERATION_TIMEOUT", "900"))

    logger.info(f"Starting generation for slug={slug} timeout={timeout_seconds}s")
    try:
        # Update task state so callers can see progress
        try:
            self.update_state(state='PROGRESS', meta={'stage': 'starting', 'slug': slug})
        except Exception:
            pass

        _log_rss(logger, "before_subprocess")

        logger.info(f"Running command: {' '.join(cmd)}")

        # Run subprocess and stream stdout/stderr to logger so we can see
        # which pipeline step is currently executing in real time.
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            start_time = time.time()

            # Read lines as they arrive and log them. Also enforce timeout_seconds.
            while True:
                # Check for timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    logger.error(f"Subprocess exceeded timeout of {timeout_seconds}s, killing process")
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise subprocess.TimeoutExpired(cmd, timeout_seconds)

                # Read stdout
                try:
                    if proc.stdout:
                        out_line = proc.stdout.readline()
                        if out_line:
                            logger.info(out_line.strip())
                            if task_log_f:
                                task_log_f.write(out_line)
                                task_log_f.flush()
                except Exception:
                    pass

                # Read stderr
                try:
                    if proc.stderr:
                        err_line = proc.stderr.readline()
                        if err_line:
                            logger.warning(err_line.strip())
                            if task_log_f:
                                task_log_f.write(err_line)
                                task_log_f.flush()
                except Exception:
                    pass

                # If process finished and pipes drained, break
                if proc.poll() is not None:
                    # drain remaining
                    try:
                        remaining_out = proc.stdout.read() if proc.stdout else ''
                        remaining_err = proc.stderr.read() if proc.stderr else ''
                        if remaining_out:
                            logger.info(remaining_out.strip())
                        if remaining_err:
                            logger.warning(remaining_err.strip())
                    except Exception:
                        pass
                    break

                time.sleep(0.1)

            returncode = proc.returncode
            logger.info(f"Subprocess finished returncode={returncode}")
            if task_log_f:
                task_log_f.write(f"Subprocess finished returncode={returncode}\n")
                task_log_f.flush()
            _log_rss(logger, "after_subprocess")

        except subprocess.TimeoutExpired as e:
            logger.error(f"TimeoutExpired after {timeout_seconds}s: {e}")
            # Ensure process is dead
            try:
                if proc and proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            if task_log_f:
                task_log_f.write(f"TimeoutExpired after {timeout_seconds}s: {e}\n")
                task_log_f.flush()
            return {"status": "failed", "error": "Tiempo de generación excedido (la IA tardó demasiado)."}
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, 'stderr') else str(e)
            logger.error(f"CalledProcessError: {stderr}")
            if task_log_f:
                task_log_f.write(f"CalledProcessError: {stderr}\n")
                task_log_f.flush()
            error_msg = f"Error en generación (IA): {stderr}"
            if "No poses found" in stderr or "Exception: No poses" in stderr:
                error_msg = "Vocabulario insuficiente: incluso tras la IA, algunas palabras no pudieron ser representadas."
            return {"status": "failed", "error": error_msg}
        except Exception as e:
            logger.exception("Unexpected error while running subprocess: %s", e)
            if task_log_f:
                task_log_f.write(f"Unexpected error: {e}\n")
                task_log_f.flush()
            return {"status": "failed", "error": "Error crítico durante la ejecución del proceso de IA."}

        if os.path.exists(output_path):
            log_emission(texto, output_path)
            _store_video_artifact(self.request.id, output_path)
            try:
                self.update_state(state='PROGRESS', meta={'stage': 'completed', 'video': output_path})
            except Exception:
                pass
            return {"status": "completed", "video_url": f"/api/video/{self.request.id}.mp4", "texto": texto}
        else:
            logger.error("Video file not found after subprocess completion")
            if task_log_f:
                task_log_f.write("Video file not found after subprocess completion\n")
                task_log_f.flush()
            return {"status": "failed", "error": "No se pudo generar el video tras el proceso de IA."}
    except subprocess.CalledProcessError as e:
        stderr = e.stderr if hasattr(e, 'stderr') else str(e)
        logger.error(f"CalledProcessError: {stderr}")
        error_msg = f"Error en generación (IA): {stderr}"
        if "No poses found" in stderr or "Exception: No poses" in stderr:
            error_msg = "Vocabulario insuficiente: incluso tras la IA, algunas palabras no pudieron ser representadas."
        if task_log_f:
            task_log_f.write(f"CalledProcessError (outer): {stderr}\n")
            task_log_f.flush()
        return {"status": "failed", "error": error_msg}
    except subprocess.TimeoutExpired as e:
        logger.error(f"TimeoutExpired after {timeout_seconds}s: {e}")
        if task_log_f:
            task_log_f.write(f"TimeoutExpired (outer) after {timeout_seconds}s: {e}\n")
            task_log_f.flush()
        return {"status": "failed", "error": "Tiempo de generación excedido (la IA tardó demasiado)."}
    finally:
        try:
            if task_log_f:
                task_log_f.write("Task finished\n")
                task_log_f.close()
        except Exception:
            pass
