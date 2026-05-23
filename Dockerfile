# ============================================================
# VozVisible — Dockerfile Multi-Servicio (Flask + Celery + Redis)
# ============================================================
FROM python:3.11-slim

# ── Dependencias del sistema ──────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Directorio de trabajo ────────────────────────────────────
WORKDIR /app

# ── Instalar dependencias de Python ──────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir gunicorn redis && \
    pip install --no-cache-dir -r requirements.txt

# ── Copiar el código del proyecto ────────────────────────────
COPY . .

# ── Crear directorios necesarios ─────────────────────────────
RUN mkdir -p assets/output secrets

# ── Variables de entorno por defecto ─────────────────────────
ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://localhost:6379/1

# ── Puerto que expone Flask/Gunicorn ─────────────────────────
EXPOSE 5002

# ── Script de arranque ───────────────────────────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
