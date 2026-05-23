"""Import custom word videos into a spoken_to_signed lexicon.

Each input video is converted to a pose file and indexed as an exact word
match, so the generator can output word-by-word signing instead of spelling.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import shutil
from pathlib import Path
from typing import Iterable

from pose_format import Pose


LEXICON_INDEX = ["path", "spoken_language", "signed_language", "start", "end", "words", "glosses", "priority"]
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def _slugify(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "entry"


def _iter_videos(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
            yield path


def _pose_duration_seconds(pose_path: Path) -> float:
    with pose_path.open("rb") as file:
        pose = Pose.read(file.read())
    return len(pose.body.data) / pose.body.fps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import word videos into a lexicon directory.")
    parser.add_argument("--input-dir", required=True, help="Directory that contains word videos")
    parser.add_argument(
        "--output-dir",
        default="spoken_to_signed/assets/custom_lexicon",
        help="Target lexicon directory that will receive the generated .pose files and index.csv",
    )
    parser.add_argument("--spoken-language", default="es", help="Spoken language code to store in index.csv")
    parser.add_argument("--signed-language", default="ase", help="Signed language code to store in index.csv")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional CSV with columns: word,video. If omitted, filenames are used as words.",
    )
    parser.add_argument(
        "--pose-format",
        default="mediapipe",
        choices=["mediapipe"],
        help="Pose estimation backend used to extract .pose files from the input videos.",
    )
    return parser


def _load_manifest(input_dir: Path, manifest_path: Path | None) -> list[tuple[str, Path]]:
    if manifest_path is None:
        return [(_slugify(video.stem), video) for video in _iter_videos(input_dir)]

    entries: list[tuple[str, Path]] = []
    with manifest_path.open(encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            word = (row.get("word") or "").strip()
            video_name = (row.get("video") or "").strip()
            if not word or not video_name:
                raise ValueError("Manifest rows must contain 'word' and 'video' columns.")
            video_path = Path(video_name)
            if not video_path.is_absolute():
                video_path = input_dir / video_path
            entries.append((word, video_path))
    return entries


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest) if args.manifest else None

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    entries = _load_manifest(input_dir, manifest_path)
    if not entries:
        raise ValueError("No input videos found.")

    output_dir.mkdir(parents=True, exist_ok=True)
    signed_dir = output_dir / args.signed_language
    signed_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for word, video_path in entries:
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        pose_name = f"{_slugify(word)}.pose"
        pose_path = signed_dir / pose_name
        subprocess.run(
            [
                "video_to_pose",
                "-i",
                str(video_path.resolve()),
                "-o",
                str(pose_path.resolve()),
                "--format",
                args.pose_format,
                "--additional-config",
                "model_complexity=1",
                "--workers",
                "1",
            ],
            check=True,
        )

        duration = _pose_duration_seconds(pose_path)
        rows.append(
            {
                "path": str(pose_path.relative_to(output_dir)),
                "spoken_language": args.spoken_language,
                "signed_language": args.signed_language,
                "start": "0",
                "end": f"{duration}",
                "words": word,
                "glosses": word,
                "priority": "0",
            }
        )

    index_path = output_dir / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LEXICON_INDEX)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Imported {len(rows)} videos into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())