import os
import sys
import argparse
import json
import resource
from pathlib import Path
from services.agents.orchestrator import run_multi_agent_pipeline

# Import the existing pipeline tools
from spoken_to_signed.bin import _gloss_to_pose
from render_skeleton_video import render_skeleton_video

DEFAULT_LEXICON = Path("spoken_to_signed/assets/lse_lexicon")
SAFE_FALLBACK_GLOSS = "HOLA"


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

        gloss_tokens = [token for token in gloss_str.split() if token.strip()]
        if not gloss_tokens:
            print("Aviso: la traducción no produjo glosas utilizables; usando fallback seguro.")
            gloss_tokens = [SAFE_FALLBACK_GLOSS]
            
        print(f"\n--- TRADUCCIÓN FINAL ---")
        print(f"Glosas: {gloss_str}")
        print(f"Velocidad: {ai_result.get('speed')}x")
        
        # 2. Convert Glosses to Pose
        sentences = _build_sentence_glosses(gloss_tokens)
        
        # 3. Lookup and Generate Pose
        # We use disable_fingerspelling=False by default to allow fallback if AI gloss isnt in lexicon
        # although the AI tries to use known glosses.
        lexicon_path = str(DEFAULT_LEXICON)
        try:
            result = _gloss_to_pose(
                sentences,
                lexicon_path,
                "es",
                "lse",
                disable_fingerspelling=False
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
                disable_fingerspelling=False
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
