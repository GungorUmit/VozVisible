import os
import sys
import subprocess
import unicodedata
import json
import uuid
import threading
import sqlite3
import glob
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

# Optional: encrypt API keys at rest (import optional to avoid native deps in dev)
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except Exception:
    Fernet = None
    CRYPTO_AVAILABLE = False

# Ensure secrets dir and fernet key
SECRETS_DIR = Path('secrets')
SECRETS_DIR.mkdir(exist_ok=True)
FERNET_PATH = SECRETS_DIR / 'fernet.key'
if CRYPTO_AVAILABLE:
    def _load_or_create_fernet():
        try:
            if not FERNET_PATH.exists():
                key = Fernet.generate_key()
                FERNET_PATH.write_bytes(key)
                return Fernet(key)

            key = FERNET_PATH.read_bytes().strip()
            try:
                return Fernet(key)
            except Exception:
                # Legacy or corrupt key: regenerate so the service can boot.
                key = Fernet.generate_key()
                FERNET_PATH.write_bytes(key)
                return Fernet(key)
        except Exception:
            return None

    FERNET = _load_or_create_fernet()
else:
    FERNET = None

from services.renfe_api import get_renfe_alerts_data

app = Flask(__name__, static_folder="static", template_folder="templates")

# DB init
def init_db():
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS emissions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, output_path TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

init_db()

def log_emission(text, output_path):
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute("INSERT INTO emissions (text, output_path) VALUES (?, ?)", (text, output_path))
    conn.commit()
    conn.close()

def set_setting(key, value):
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_encrypted_setting(key, value):
    """Encrypt and store a setting value."""
    if FERNET is None:
        # cryptography not available — store plain
        set_setting(key, value)
        return
    try:
        token = FERNET.encrypt(value.encode()).decode()
        set_setting(key, token)
    except Exception:
        # fallback to plain storage
        set_setting(key, value)


def get_encrypted_setting(key):
    """Retrieve and decrypt a setting value if possible."""
    val = get_setting(key)
    if not val:
        return None
    if FERNET is None:
        return val
    try:
        # try decrypting
        dec = FERNET.decrypt(val.encode()).decode()
        return dec
    except Exception:
        return val

# Cargar frases desde el archivo JSON
def load_frases():
    try:
        with open("data/frases_transporte.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

FRASES = load_frases()

def _slugify(t: str) -> str:
    normalized = unicodedata.normalize("NFKD", t)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in ascii_text.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "video"

jobs = {}

def generate_video_task(job_id, texto, slug, env):
    output_path = f"assets/output/{slug}.mp4"
    os.makedirs("assets/output", exist_ok=True)
    
    if os.path.exists(output_path):
        log_emission(texto, output_path)
        jobs[job_id] = {"status": "completed", "video_url": f"/{output_path}", "texto": texto, "cached": True}
        return

    cmd = [sys.executable, "generate_video.py", "--text", texto, "--output", output_path, "--disable-fingerspelling"]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env, timeout=120)
        if os.path.exists(output_path):
            log_emission(texto, output_path)
            jobs[job_id] = {"status": "completed", "video_url": f"/{output_path}", "texto": texto}
        else:
            jobs[job_id] = {"status": "failed", "error": "No se pudo generar el video."}
    except subprocess.CalledProcessError as e:
        error_msg = f"Error en generación: {e.stderr}"
        if "not found" in e.stderr or "Exception: No poses" in e.stderr:
            error_msg = "Vocabulario insuficiente: algunas palabras no están en la base de datos LSE."
        jobs[job_id] = {"status": "failed", "error": error_msg}
    except subprocess.TimeoutExpired:
        jobs[job_id] = {"status": "failed", "error": "Tiempo de generación excedido."}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("assets", filename)

@app.route("/api/alerts")
def get_alerts():
    result = get_renfe_alerts_data()
    if not result.get("success"):
        return jsonify({"error": result.get("error"), "alerts": []}), 500
    
    return jsonify({
        "total": result.get("total"),
        "timestamp": result.get("timestamp"),
        "alerts": result.get("alerts")
    })

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    tipo = data.get("tipo", "")
    texto_custom = data.get("texto", "")

    if tipo and tipo in FRASES:
        texto = FRASES[tipo]
    elif texto_custom:
        texto = texto_custom
    else:
        return jsonify({"error": "No se ha proporcionado texto ni tipo de aviso."}), 400

    slug = _slugify(texto)
    env = os.environ.copy()
    groq_key = data.get("api_key") or get_encrypted_setting('groq_api_key')
    if groq_key:
        env["GROQ_API_KEY"] = groq_key
        env["OPENAI_API_KEY"] = groq_key
    # Submit generation as a Celery task
    from tasks import async_generate_video
    task = async_generate_video.apply_async(args=(texto, slug, env))
    return jsonify({"job_id": task.id, "status": "processing"})

@app.route("/api/status/<job_id>")
def check_status(job_id):
    from tasks import celery_app
    task = celery_app.AsyncResult(job_id)
    state = task.state
    if state in ("PENDING", "RECEIVED", "STARTED"):
        return jsonify({"status": "processing"})
    if state == "SUCCESS":
        return jsonify(task.result)
    if state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.result)})
    return jsonify({"status": state})


@app.route('/api/save-api-key', methods=['POST'])
def save_api_key():
    data = request.get_json() or {}
    key = data.get('api_key')
    if not key:
        return jsonify({'error': 'No api_key provided'}), 400
    try:
        set_encrypted_setting('groq_api_key', key)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-api-key')
def get_api_key():
    key = get_encrypted_setting('groq_api_key')
    if not key:
        return jsonify({'api_key_masked': None})
    mask = (key[:4] + '...' + key[-4:]) if len(key) > 8 else '********'
    return jsonify({'api_key_masked': mask})

@app.route("/api/clear-cache", methods=["POST"])
def clear_cache():
    try:
        files = glob.glob("assets/output/*.mp4")
        now = time.time()
        deleted = 0
        for f in files:
            # Prevent deleting predefined base videos if needed
            # Delete if older than 48 hours (48 * 3600 seconds)
            try:
                if os.path.getmtime(f) < now - (48 * 3600):
                    os.remove(f)
                    deleted += 1
            except Exception:
                continue
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import threading
# Auto-cleanup thread kept for backward compatibility in dev mode,
# but in production use Celery Beat `cleanup_old_outputs` task.
def auto_cleanup_task():
    while True:
        try:
            files = glob.glob("assets/output/*.mp4")
            now = time.time()
            for f in files:
                try:
                    if os.path.getmtime(f) < now - (48 * 3600):
                        os.remove(f)
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(12 * 3600) # Run every 12 hours

threading.Thread(target=auto_cleanup_task, daemon=True).start()

@app.route("/api/logs")
def get_logs():
    conn = sqlite3.connect('logs.db')
    c = conn.cursor()
    c.execute("SELECT id, text, timestamp FROM emissions ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    
    logs = [{"id": r[0], "text": r[1], "timestamp": r[2]} for r in rows]
    return jsonify({"logs": logs})

if __name__ == "__main__":
    app.run(debug=True, port=5002, host="0.0.0.0")
@app.route("/api/whatsapp")
def get_whatsapp():
    # Simulador (Mock) del Canal Oficial de WhatsApp para Cercanías Madrid
    import time
    now = int(time.time())
    messages = [
        {
            "id": "wa_1",
            "texto": "🚆 Línea C5\n\n🟡 Los trenes, sentido Fuenlabrada-Humanes, están sufriendo demoras, detenciones y pueden ver variado su recorrido habitual.\n\n⚠️ Avería de un tren en la estación de Doce de Octubre.",
            "timestamp": now - 300,
            "es_madrid": True
        },
        {
            "id": "wa_2",
            "texto": "📢 ACTUALIZACIÓN\n\n🚆 Línea C-5\n\n✅ Una vez retirado el tren de la estación de Doce de Octubre. Los trenes recuperan sus frecuencias de paso de forma progresiva.",
            "timestamp": now - 1800,
            "es_madrid": True
        },
        {
            "id": "wa_3",
            "texto": "🚆 Líneas C-2 / C-7 / C-8\n\n🟡 Los trenes, sentido Atocha-Chamartín, sufren demoras, detenciones y pueden ver modificado su recorrido habitual.\n\n⚠️ Avería de un tren en la estación de Vallecas.",
            "timestamp": now - 3600,
            "es_madrid": True
        },
        {
            "id": "wa_4",
            "texto": "🚆 Línea C-1\n\n🔴 Tren con salida de Chamartín a las 17:28h y llegada a Aeropuerto T4 a las 17:35h, hoy, no circula.\n\nℹ️ Próximo tren con origen Chamartín y destino Aeropuerto T4, tiene prevista su salida a las 17:35h, aproximadamente.\n\n⚠️ Reajuste del servicio.",
            "timestamp": now - 7200,
            "es_madrid": True
        }
    ]
    return jsonify({"messages": messages})

@app.route('/api/metro_x')
def get_metro_x():
    """Mock for Metro de Madrid X (Twitter) channel feed."""
    now = time.time()
    # Simulate some realistic Metro de Madrid tweets
    messages = [
        {
            "id": "x_1",
            "texto": "🔴 Circulación interrumpida en L6 entre las estaciones de Sainz de Baranda y Pacífico, en ambos sentidos, por asistencia sanitaria. Tiempo estimado de solución más de 15 minutos.",
            "timestamp": now - 600,
            "es_madrid": True
        },
        {
            "id": "x_2",
            "texto": "✅ Restablecido el servicio en L6 entre Sainz de Baranda y Pacífico. Los trenes vuelven a circular con normalidad.",
            "timestamp": now - 3600,
            "es_madrid": True
        },
        {
            "id": "x_3",
            "texto": "⚠️ Circulación lenta en L10 entre Tres Olivos y Begoña, sentido Puerta del Sur, por incidencia en las instalaciones.",
            "timestamp": now - 7200,
            "es_madrid": True
        }
    ]
    return jsonify({"messages": messages})

