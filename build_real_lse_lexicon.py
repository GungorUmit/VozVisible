#!/usr/bin/env python3
"""Build an LSE lexicon by converting videos to pose files using pose-format's CLI.

This script converts each video in `spoken_to_signed/videos_lse` to a `.pose`
using the installed `video_to_pose` CLI (MediaPipe), then writes an `index.csv`
under `spoken_to_signed/assets/lse_lexicon` with lemma-based glosses to improve
lookup from `text_to_gloss`.
"""

import csv
import subprocess
from pathlib import Path
from simplemma import text_lemmatizer
from pose_format import Pose


def lemmatize(word: str) -> str:
    try:
        lem = list(text_lemmatizer(word, lang="es"))
        return lem[0] if lem else word
    except Exception:
        return word


def main():
    videos_dir = Path("spoken_to_signed/videos_lse")
    out_dir = Path("spoken_to_signed/assets/lse_lexicon/lse")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    video_files = sorted(list(videos_dir.glob("*.mp4")) + list(videos_dir.glob("*.mov")))
    if not video_files:
        print("No videos found in", videos_dir)
        return 1

    for video in video_files:
        stem = video.stem
        pose_path = out_dir / f"lse-{stem}.pose"
        print("Converting:", video.name)

        cmd = [
            "video_to_pose",
            "-i",
            str(video),
            "-o",
            str(pose_path),
            "--format",
            "mediapipe",
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print("  ✗ conversion failed:", e)
            continue

        try:
            with open(pose_path, "rb") as f:
                pose = Pose.read(f.read())
            num_frames = len(pose.body.data)
        except Exception as e:
            print("  ✗ reading pose failed:", e)
            continue

        gloss = lemmatize(stem)
        rows.append({
            "path": f"lse/lse-{stem}.pose",
            "spoken_language": "es",
            "signed_language": "lse",
            "start": 0,
            "end": num_frames - 1,
            "words": stem,
            "glosses": gloss.upper(),
            "priority": 0,
        })

        print(f"  ✓ wrote pose ({num_frames} frames)")

    index_path = Path("spoken_to_signed/assets/lse_lexicon/index.csv")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "path",
            "spoken_language",
            "signed_language",
            "start",
            "end",
            "words",
            "glosses",
            "priority",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print("\n✓ LSE lexicon built:", index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
