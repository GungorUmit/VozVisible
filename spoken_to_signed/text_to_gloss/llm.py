import os
from .types import Gloss, GlossItem

def text_to_gloss(text: str, language: str, **unused_kwargs) -> list[Gloss]:
    """Uses an LLM via OpenAI API to translate Spanish text to LSE glosses."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set. Cannot use LLM glosser.")
        
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Please install the 'openai' package to use the LLM backend.")
        
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    prompt = (
        "Eres un traductor experto de español a glosas de Lengua de Signos Española (LSE). "
        "Tu tarea es convertir la frase de entrada en una secuencia de glosas naturales y útiles para renderizado LSE. "
        "Reglas estrictas: "
        "1. Prohibido fingerspelling y prohibido deletrear letra por letra. "
        "2. Prohibido usar símbolos o marcas de spelling como %, ⌘, paréntesis de spelling, letras separadas por espacios o secuencias alfabéticas. "
        "3. Si un nombre propio o una palabra no tiene glosa clara, reformula la frase con una glosa funcional o semánticamente equivalente. "
        "4. Si hace falta, omite palabras vacías que no aportan significado signado. "
        "5. Prioriza siempre glosas reales de LSE sobre traducciones literales. "
        "6. Usa orden natural de LSE cuando sea necesario para mantener claridad. "
        "7. Devuelve únicamente las glosas finales separadas por espacios, sin explicación, sin puntuación extra y sin comillas. "
        "8. Devuelve todo en minúsculas. "
        "9. Si dudas entre deletrear o reformular, siempre reformula.\n"
        f"Frase original: '{text}'"
    )
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    output = response.choices[0].message.content.strip()
    print(f"[LLM Traducción LSE]: '{text}' -> '{output}'")
    
    glosses = []
    for token in output.split():
        clean_token = token.strip(",.").lower()
        if clean_token:
            glosses.append(GlossItem(word=clean_token, gloss=clean_token))
            
    return [glosses]