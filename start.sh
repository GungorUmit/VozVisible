#!/bin/bash
set -e

echo "🚀 VozVisible — Arrancando servicios..."

# ── 1. Redis ─────────────────────────────────────────────────
echo "📦 Iniciando Redis..."
redis-server --daemonize yes --port 6379

# Esperar a que Redis esté listo
until redis-cli ping | grep -q PONG; do
  echo "   ⏳ Esperando a Redis..."
  sleep 0.5
done
echo "✅ Redis listo."

# ── 2. Celery Worker ─────────────────────────────────────────
echo "⚙️  Iniciando Celery Worker..."
# Set conservative limits for long-running AI/video generation tasks.
CELERY_TIME_LIMIT=${CELERY_TIME_LIMIT:-900}
CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-1}
CELERY_MAX_TASKS_PER_CHILD=${CELERY_MAX_TASKS_PER_CHILD:-5}
CELERY_MAX_MEMORY_PER_CHILD=${CELERY_MAX_MEMORY_PER_CHILD:-220000}
CELERY_PREFETCH_MULTIPLIER=${CELERY_PREFETCH_MULTIPLIER:-1}
export AI_GENERATION_TIMEOUT=${AI_GENERATION_TIMEOUT:-900}
celery -A tasks worker --loglevel=info \
  --concurrency=${CELERY_CONCURRENCY} \
  --time-limit=${CELERY_TIME_LIMIT} \
  --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD} \
  --max-memory-per-child=${CELERY_MAX_MEMORY_PER_CHILD} \
  --prefetch-multiplier=${CELERY_PREFETCH_MULTIPLIER} &
CELERY_PID=$!
sleep 2
echo "✅ Celery Worker arrancado (PID: $CELERY_PID)."

# ── 3. Flask via Gunicorn ────────────────────────────────────
echo "🌐 Iniciando servidor web (Gunicorn)..."
PORT=${PORT:-5002}
exec gunicorn server:app \
  --bind "0.0.0.0:$PORT" \
  --workers 2 \
  --timeout 900 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --access-logfile - \
  --error-logfile -
