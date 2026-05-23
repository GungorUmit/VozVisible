"""Generate a word-by-word demo video from user-provided clips.

This path bypasses pose estimation entirely: each token is mapped to a video
clip, and the clips are concatenated in the order of the input text.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path
from typing import Iterable

try:
    import cv2
    import numpy as np
except ImportError as exc:  # pragma: no cover - dependency check
    raise ImportError("Please install opencv-python to use generate_word_video.py") from exc


DEFAULT_OUTPUT_DIR = Path("assets/output")
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in ascii_text.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "entry"


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ]+", text, flags=re.UNICODE) if token]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a video by concatenating per-word clips.")
    parser.add_argument("--text", required=True, help="Text to convert into a clip sequence")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing one video clip per word. Filenames should match the words.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional CSV with columns: word,video. If omitted, filenames are used as words.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output video path. Defaults to assets/output/<slug>.mp4",
    )
    parser.add_argument(
        "--gap-seconds",
        type=float,
        default=0.0,
        help="Optional black gap inserted between word clips.",
    )
    return parser


def _iter_videos(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
            yield path


def _load_manifest(input_dir: Path, manifest_path: Path | None) -> dict[str, Path]:
    entries: dict[str, Path] = {}

    if manifest_path is None:
        for video_path in _iter_videos(input_dir):
            entries[_slugify(video_path.stem)] = video_path
        return entries

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

            entries[_slugify(word)] = video_path

    return entries


def _read_video_frames(video_path: Path) -> tuple[list, float, tuple[int, int]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frames = []
    while True:
        success, frame = capture.read()
        if not success:
            break
        frames.append(frame)

    capture.release()

    if not frames:
        raise ValueError(f"Video has no frames: {video_path}")

    return frames, fps, (width, height)


def _write_video(frames: list, output_path: Path, fps: float, size: tuple[int, int]):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not create output video: {output_path}")

    for frame in frames:
        if frame.shape[1] != size[0] or frame.shape[0] != size[1]:
            frame = cv2.resize(frame, size)
        writer.write(frame)

    writer.release()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    input_dir = Path(args.input_dir)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"{_slugify(args.text)}.mp4"
    manifest_path = Path(args.manifest) if args.manifest else None

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    word_to_video = _load_manifest(input_dir, manifest_path)
    words = [_slugify(token) for token in _tokenize(args.text)]
    if not words:
        raise ValueError("No words found in the input text.")

    missing = [word for word in words if word not in word_to_video]
    if missing:
        raise FileNotFoundError(
            "Missing clips for: " + ", ".join(missing) + ". Ensure filenames or manifest entries match those words."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    stitched_frames = []
    target_fps = 25.0
    target_size: tuple[int, int] | None = None

    for index, word in enumerate(words):
        frames, fps, size = _read_video_frames(word_to_video[word])
        if target_size is None:
            target_size = size
            target_fps = fps

        stitched_frames.extend(frames)

        if args.gap_seconds > 0 and index < len(words) - 1:
            gap_frame_count = max(1, int(round(target_fps * args.gap_seconds)))
            black_frame = np.zeros((target_size[1], target_size[0], 3), dtype=frames[-1].dtype)
            stitched_frames.extend([black_frame] * gap_frame_count)

    assert target_size is not None
    _write_video(stitched_frames, output_path, target_fps, target_size)

    print(f"Video generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())