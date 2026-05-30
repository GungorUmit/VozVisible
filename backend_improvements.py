import os
import sys
import argparse
import json
import csv
import resource
from pathlib import Path
from services.agents.orchestrator import run_multi_agent_pipeline

# Import the existing pipeline tools
from spoken_to_signed.bin import _gloss_to_pose
from render_skeleton_video import render_skeleton_video

DEFAULT_LEXICON = Path("spoken_to_signed/assets/lse_lexicon")
SAFE_FALLBACK_GLOSS = "TREN"
_ALLOWED_GLOSSES = None


def _load_allowed_glosses():
    global _ALLOWED_GLOSSES
    if _ALLOWED_GLOSSES is not None:
        return _ALLOWED_GLOSSES

    index_path = DEFAULT_LEXICON / "index.csv"
    allowed = set()
    with index_path.open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            for key in ("words", "glosses"):
                value = (row.get(key) or "").strip()
                if value:
                    allowed.add(value.lower())
    _ALLOWED_GLOSSES = allowed
    return allowed


def _normalize_gloss_tokens(gloss_str):
    tokens = [token.strip() for token in gloss_str.split() if token.strip()]
    allowed = _load_allowed_glosses()
    # Avoid letter-by-letter output and any token not present in the LSE lexicon.
    filtered = [token for token in tokens if len(token) > 1 and not token.isdigit() and token.lower() in allowed]
    return filtered or [SAFE_FALLBACK_GLOSS]


def _build_sentence_glosses(gloss_tokens):
    from spoken_to_signed.text_to_gloss.types import GlossItem

    return [[GlossItem(word=token.lower(), gloss=token.lower()) for token in gloss_tokens]]


def _log_rss(prefix):
    try:
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(f"[{prefix}] rss_kb={rss_kb}")
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Generate LSE video using Multi-Agent AI Orchestrator")
    parser.add_argument("--text", required=True, help="Spanish text to translate")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--api-key", help="Groq API Key (optional if set in env)")
    
    args = parser.parse_args()
    
    api_key = args.api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: No GROQ_API_KEY found.")
        sys.exit(1)
        
    print(f"--- MENTE DE LA IA ---")
    print(f"Entrada: {args.text}")
    
    # 1. Run the Multi-Agent Pipeline
    try:
        _log_rss("before_pipeline")
        # Note: run_multi_agent_pipeline returns {clean_text, glosses, speed}
        # we can pass a log_callback to see the "thoughts" of the agents
        def _shorten(v, max_len=200):
            try:
                if v is None:
                    return "<none>"
                # If it's a list/tuple/ndarray-like, summarize
                if isinstance(v, (list, tuple)):
                    return f"<{type(v).__name__} len={len(v)}>"
                s = str(v)
                if len(s) > max_len:
                    return s[:max_len] + "...<truncated>"
                return s
            except Exception:
                return "<unserializable>"

        def log_step(data):
            role = data.get("role", "system").upper()
            msg = data.get("msg", "")
            safe_msg = _shorten(msg)
            print(f"[{role}] {safe_msg}")

        ai_result = run_multi_agent_pipeline(args.text, api_key, log_callback=log_step)
        _log_rss("after_pipeline")
        
        gloss_str = ai_result.get("glosses")
        if not gloss_str:
            print("Error: El orquestador no devolvió glosas.")
            sys.exit(1)

        gloss_tokens = _normalize_gloss_tokens(gloss_str)
        if gloss_tokens == [SAFE_FALLBACK_GLOSS]:
            print("Aviso: la traducción no produjo glosas utilizables; usando fallback seguro.")
            
        print(f"\n--- TRADUCCIÓN FINAL ---")
        print(f"Glosas: {gloss_str}")
        print(f"Velocidad: {ai_result.get('speed')}x")
        
        # 2. Convert Glosses to Pose
        sentences = _build_sentence_glosses(gloss_tokens)
        
        # 3. Lookup and Generate Pose
        # Keep the pipeline off fingerspelling entirely; only full glosses are rendered.
        lexicon_path = str(DEFAULT_LEXICON)
        try:
            result = _gloss_to_pose(
                sentences,
                lexicon_path,
                "es",
                "lse",
                disable_fingerspelling=True
            )
            _log_rss("after_lookup")
        except Exception as lookup_error:
            print(f"Aviso: fallo el lookup principal ({lookup_error}); usando fallback seguro.")
            fallback_sentences = _build_sentence_glosses([SAFE_FALLBACK_GLOSS])
            result = _gloss_to_pose(
                fallback_sentences,
                lexicon_path,
                "es",
                "lse",
                disable_fingerspelling=True
            )
            _log_rss("after_fallback_lookup")
        
        # 4. Render Video
        _log_rss("before_render")
        render_skeleton_video(result.pose, args.output)
        _log_rss("after_render")
        print(f"Video generado exitosamente: {args.output}")
        
    except Exception as e:
        print(f"Error crítico en el pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
