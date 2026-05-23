import os
import csv
from pathlib import Path

LEXICON_DIR = Path("spoken_to_signed/assets/lse_lexicon")
LSE_DIR = LEXICON_DIR / "lse"
INDEX_CSV = LEXICON_DIR / "index.csv"

# Extra synonyms / mappings based on the predefined dashboard phrases to ensure a high match rate.
EXTRA_MAPPINGS = {
    "ahora": ["ahora", "próxima", "proxima", "próximo", "proximo"],
    "molestar": ["molestar", "molestias", "disculpen"],
    "cuidado": ["cuidado", "cuidar", "atención", "atencion"],
    "desalojar": ["desalojar", "desalojen", "salir"],
    "funcionar": ["funcionar", "funcionamiento"],
    "interrumpido": ["interrumpido", "avería", "averia", "interrumpir"],
    "parada": ["parada", "estación", "estacion"],
    "estacion": ["estacion", "estación", "parada"],
    "llegar": ["llegar", "llegada", "llega", "destino"],
    "salir": ["salir", "salida", "efectuar", "sale"],
    "tren": ["tren", "coche"],
    "via": ["via", "vía"],
    "andén": ["anden", "andén"], # Handle unicode decomposed characters if needed
    "anden": ["anden", "andén"],
    "línea": ["linea", "línea", "líneas", "lineas"],
    "linea": ["linea", "línea", "líneas", "lineas"]
}

def rebuild_index():
    if not LSE_DIR.exists():
        print(f"Error: Directory {LSE_DIR} does not exist.")
        return

    # Gather all pose files
    pose_files = list(LSE_DIR.glob("*.pose"))
    print(f"Found {len(pose_files)} pose files.")

    rows = []
    
    # Also we keep track of already added rows so we don't duplicate perfectly identical ones
    seen = set()

    for p in pose_files:
        filename = p.name
        # Base name without .pose and without lse- prefix
        base_word = p.stem.replace("lse-", "")
        
        # We start with the base word itself
        mappings = [base_word]
        
        # Add any extra synonyms we defined
        if base_word in EXTRA_MAPPINGS:
            mappings.extend(EXTRA_MAPPINGS[base_word])
            
        # Clean up duplicates in mappings
        mappings = list(dict.fromkeys(mappings))
        
        for m in mappings:
            # We add a row for this word
            row = {
                "path": f"lse/{filename}",
                "spoken_language": "es",
                "signed_language": "lse",
                "start": "0",
                "end": "0",
                "words": m,
                "glosses": m,
                "priority": "0"
            }
            row_tuple = tuple(row.items())
            if row_tuple not in seen:
                seen.add(row_tuple)
                rows.append(row)

    print(f"Generated {len(rows)} rows for index.csv.")

    # Write to index.csv
    with open(INDEX_CSV, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["path", "spoken_language", "signed_language", "start", "end", "words", "glosses", "priority"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Successfully wrote {INDEX_CSV}.")

if __name__ == '__main__':
    rebuild_index()
