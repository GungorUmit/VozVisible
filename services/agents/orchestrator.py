import json
import re
from openai import OpenAI
from .prompts import (
    SYSTEM_PROMPT_CONTEXT_AGENT,
    SYSTEM_PROMPT_LINGUIST_AGENT,
    SYSTEM_PROMPT_CRITIC_AGENT,
    SYSTEM_PROMPT_ANIMATOR_AGENT
)

# Utilizaremos llama-3.1 para el modelo rápido y llama-3.3 para el complejo
MODEL_FAST = "llama-3.1-8b-instant"
MODEL_SMART = "llama-3.3-70b-versatile"

def get_client(api_key: str):
    if not api_key:
        raise ValueError("GROQ_API_KEY no proporcionada para los agentes.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

def _call_agent(client, system_prompt: str, user_input: str, model=MODEL_FAST, temperature=0.2) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=temperature,
        max_tokens=256
    )
    return response.choices[0].message.content.strip()


def _normalize_gloss_output(raw_output: str) -> str:
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", raw_output)
    return " ".join(token.upper() for token in tokens)

def run_multi_agent_pipeline(raw_text: str, api_key: str, log_callback=None) -> dict:
    """
    Orquesta la ejecución de los 4 agentes.
    Retorna un diccionario con los resultados.
    """
    def log(msg, role="system"):
        print(msg)
        if log_callback:
            log_callback({"role": role, "msg": msg})

    try:
        client = get_client(api_key)
    except Exception as e:
        log(f"[Orchestrator] Error de autenticación: {e}", "error")
        # Fallback de seguridad si falla la key
        return {"clean_text": raw_text, "glosses": None, "speed": 1.0}

    log(f"Analizando texto bruto: '{raw_text}'", "filtro")
    clean_text = _call_agent(client, SYSTEM_PROMPT_CONTEXT_AGENT, raw_text, model=MODEL_FAST)
    log(f"Texto extraído: '{clean_text}'", "filtro")

    log(f"Evaluando urgencia para adaptar velocidad...", "animador")
    speed_json_str = _call_agent(client, SYSTEM_PROMPT_ANIMATOR_AGENT, clean_text, model=MODEL_FAST)
    speed = 1.0
    try:
        speed_data = json.loads(speed_json_str)
        speed = float(speed_data.get("speed", 1.0))
    except Exception:
        log(f"Fallo al parsear urgencia, usando 1.0x por defecto.", "error")
    log(f"Velocidad de signado asignada: {speed}x", "animador")

    # Bucle Adversarial (Traductor vs Crítico)
    log(f"Traduciendo a Lengua de Signos...", "traductor")
    glosses = _normalize_gloss_output(
        _call_agent(client, SYSTEM_PROMPT_LINGUIST_AGENT, clean_text, model=MODEL_SMART, temperature=0.1)
    )
    
    max_retries = 2
    for attempt in range(max_retries):
        log(f"Glosas propuestas (Intento {attempt+1}): {glosses}", "traductor")
        log(f"Revisando accesibilidad e impacto visual...", "critico")
        
        critic_feedback = _call_agent(client, SYSTEM_PROMPT_CRITIC_AGENT, glosses, model=MODEL_FAST)
        
        if critic_feedback.startswith("EXCELENTE"):
            log("Traducción APROBADA. Las glosas son correctas y fluidas.", "critico")
            break
        else:
            log(f"Traducción RECHAZADA. Motivo: {critic_feedback}", "critico")
            log("Reescribiendo glosas para corregir el error...", "traductor")
            correction_prompt = f"Tu traducción anterior fue: '{glosses}'. El auditor sordo la ha RECHAZADO con este motivo: '{critic_feedback}'. Por favor, reescribe las glosas corrigiendo este error. Recuerda usar SOLO MAYÚSCULAS y separar por espacios. ESTRICTAMENTE DEVUELVE SOLO LAS GLOSAS, NINGUNA OTRA PALABRA NI EXPLICACIÓN."
            glosses = _normalize_gloss_output(
                _call_agent(client, SYSTEM_PROMPT_LINGUIST_AGENT, correction_prompt, model=MODEL_SMART, temperature=0.2)
            )
            
    return {
        "clean_text": clean_text,
        "glosses": glosses,
        "speed": speed
    }
