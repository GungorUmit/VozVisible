import json
import os
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from spoken_to_signed.text_to_gloss.types import Gloss, GlossItem

SYSTEM_PROMPT = """
Eres un traductor experto de español a glosas de Lengua de Signos Española (LSE).

Objetivo:
Convertir el texto de entrada en glosas naturales de LSE, priorizando significado, claridad y renderizado sin fingerspelling.

Reglas estrictas:
1. Prohibido fingerspelling.
2. Prohibido deletrear nombres, siglas, marcas o palabras letra por letra.
3. Prohibido usar símbolos o notaciones de spelling como %, ⌘, paréntesis de spelling, letras separadas por espacios o secuencias alfabéticas.
4. Si una palabra no tiene una glosa clara, reformula la frase con una glosa funcional o semánticamente equivalente.
5. Si hace falta, omite artículos, determinantes y preposiciones vacías.
6. Prioriza glosas reales de LSE sobre traducción literal.
7. Mantén nombres propios solo si pueden tratarse como glosa semántica; nunca los deletrees.
8. Devuelve únicamente una lista JSON válida de sentences, sin explicación adicional.
9. Cada sentence debe ser una cadena de glosas separadas por espacios, sin puntuación extra.
10. Si dudas entre deletrear o reformular, siempre reformula.

Estilo:
- Preferencia por orden natural de LSE.
- Salida compacta y directamente utilizable para el pipeline.
- No introduzcas texto fuera del JSON final.
""".strip()


@lru_cache(maxsize=1)
def get_openai_client():
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", None)
    return OpenAI(api_key=api_key)


@lru_cache(maxsize=1)
def few_shots():
    data_path = Path(__file__).parent / "few_shots.json"
    with open(data_path, encoding="utf-8") as file:
        data = json.load(file)

    messages = []
    for entry in data:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "spoken_language": entry["spoken_language"],
                        "signed_language": entry["signed_language"],
                        "text": entry["text"],
                    }
                ),
            }
        )
        messages.append({"role": "assistant", "content": json.dumps(entry["sentences"])})

    return messages


def sentence_to_glosses(sentence: str) -> Iterator[GlossItem]:
    for item in sentence.split(" "):
        regex_with_mouthing = r"⌘(.*?)\((.*?)\)"
        if match := re.match(regex_with_mouthing, item):
            match.group(1)
            content = match.group(2)
        else:
            content = item
        for sub_item in content.split(" "):
            if "/" in sub_item:
                sub_item_gloss, sub_item_word = sub_item.split("/")
            else:
                sub_item_gloss = sub_item_word = sub_item
            yield GlossItem(word=sub_item_word, gloss=sub_item_gloss)


def text_to_gloss(text: str, language: str, signed_language: str, **kwargs) -> list[Gloss]:
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + few_shots()
        + [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "spoken_language": language,
                        "signed_language": signed_language,
                        "text": text,
                    }
                ),
            }
        ]
    )

    response = get_openai_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0, seed=42, messages=messages, max_tokens=500
    )

    prediction = response.choices[0].message.content
    print(prediction)
    sentences = json.loads(prediction)
    return [list(sentence_to_glosses(sentence)) for sentence in sentences]


if __name__ == "__main__":
    text = "Kleine kinder essen pizza."
    language = "de"
    signed_language = "sgg"
    print(text_to_gloss(text, language, signed_language))
