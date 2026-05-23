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
# Set generous time limits for long-running AI/video generation tasks (default 900s)
CELERY_TIME_LIMIT=${CELERY_TIME_LIMIT:-900}
export AI_GENERATION_TIMEOUT=${AI_GENERATION_TIMEOUT:-900}
celery -A tasks worker --loglevel=info --concurrency=2 --time-limit=${CELERY_TIME_LIMIT} &
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
  --access-logfile - \
  --error-logfile -
