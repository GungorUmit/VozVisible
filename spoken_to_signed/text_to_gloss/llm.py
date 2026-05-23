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
        "Eres un intérprete experto en Lengua de Signos Española (LSE). "
        "Tu tarea es convertir la siguiente frase en español a glosas de LSE. "
        "Reglas: "
        "1. Omite determinantes (el, la, los), artículos y preposiciones que no aportan significado. "
        "2. Pon los verbos en infinitivo. "
        "3. Estructura la frase típicamente como Tiempo-Lugar-Sujeto-Objeto-Verbo. "
        "4. Devuelve ÚNICAMENTE los términos resultantes separados por espacios, sin signos de puntuación extra. "
        "5. Devuelve todo en minúsculas.\n"
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