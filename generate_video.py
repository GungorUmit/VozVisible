"""Generate a spoken-to-signed demo video from plain text.

This is a small convenience wrapper around the existing spoken_to_signed
pipeline so the demo can be run with one command.
"""

from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path
from typing import Optional

from spoken_to_signed.bin import _gloss_to_pose, _pose_to_video, _text_to_gloss
from render_skeleton_video import render_skeleton_video


DEFAULT_LEXICON = Path("spoken_to_signed/assets/lse_lexicon")
DEFAULT_OUTPUT_DIR = Path("assets/output")


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in ascii_text.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "video"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a demo video from spoken text using spoken_to_signed."
    )
    parser.add_argument("--text", required=True, help="Text to convert into sign video")
    parser.add_argument(
        "--spoken-language",
        default="es",
        help="Spoken language code used by the text-to-gloss step",
    )
    parser.add_argument(
        "--signed-language",
        default="lse",
        help="Signed language code used by the lexicon lookup",
    )
    parser.add_argument(
        "--glosser",
        default="llm",
        choices=["simple", "spacylemma", "rules", "lse_rules", "nmt", "llm"],
        help="Text-to-gloss backend",
    )
    parser.add_argument(
        "--lexicon",
        default=str(DEFAULT_LEXICON),
        help="Path to the lexicon directory that contains index.csv",
    )
    parser.add_argument(
        "--lookup-language",
        default=None,
        help="Override the spoken-language code used for lexicon lookup",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output video path. Defaults to assets/output/<slug>.mp4",
    )
    parser.add_argument(
        "--disable-fingerspelling",
        action="store_true",
        help="Disable the fingerspelling fallback when a gloss is missing",
    )
    parser.add_argument(
        "--renderer",
        default="skeleton",
        choices=["skeleton", "pix2pix"],
        help="Video renderer to use. 'skeleton' draws the avatar directly as a pose skeleton.",
    )
    return parser


def _resolve_lookup_language(lexicon: Path, spoken_language: str, signed_language: str) -> str:
    index_path = lexicon / "index.csv"
    if not index_path.exists():
        return spoken_language

    with index_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    for row in rows:
        if row.get("spoken_language") == spoken_language and row.get("signed_language") == signed_language:
            return spoken_language

    for row in rows:
        if row.get("spoken_language") == "en" and row.get("signed_language") == signed_language:
            return "en"

    return spoken_language


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    lexicon = Path(args.lexicon)
    if not lexicon.exists():
        raise FileNotFoundError(f"Lexicon directory not found: {lexicon}")

    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"{_slugify(args.text)}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lookup_language = args.lookup_language or _resolve_lookup_language(
        lexicon, args.spoken_language, args.signed_language
    )

    sentences = _text_to_gloss(args.text, args.spoken_language, args.glosser)
    result = _gloss_to_pose(
        sentences,
        str(lexicon),
        lookup_language,
        args.signed_language,
        args.disable_fingerspelling,
    )
    if args.renderer == "skeleton":
        render_skeleton_video(result.pose, str(output_path))
    else:
        _pose_to_video(result.pose, str(output_path))

    print(f"Video generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())