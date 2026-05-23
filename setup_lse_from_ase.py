#!/usr/bin/env python3
"""Map existing ASE poses to Spanish/LSE words as a workaround.

This creates a usable lexicon while direct video->pose extraction is failing.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from pose_format import Pose


def copy_pose_file(src_path: Path, dest_path: Path):
    """Copy a pose file."""
    with open(src_path, 'rb') as f:
        data = f.read()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, 'wb') as f:
        f.write(data)


@dataclass
class WordEntry:
    word: str
    pose_file: Path


def _duration_ms(pose: Pose) -> int:
    # lookup.py expects start/end in milliseconds, not frame indices.
    frames = len(pose.body.data)
    return int((frames / pose.body.fps) * 1000)


def main():
    ase_lexicon = Path("spoken_to_signed/assets/fingerspelling_lexicon/ase")
    lse_lexicon = Path("spoken_to_signed/assets/lse_lexicon/lse")
    
    if not ase_lexicon.exists():
        print("✗ ASE lexicon not found")
        return 1
    
    lse_lexicon.mkdir(parents=True, exist_ok=True)
    
    # Target words/variants needed for phrase-level generation.
    # We intentionally include inflected forms to avoid misses in lookup.
    target_words = [
        "el",
        "en",
        "tren",
        "salir",
        "sale",
        "cinco",
        "5",
        "minuto",
        "minutos",
        "llegar",
    ]
    
    # Find ASE pose files
    ase_poses = {}
    for pose_file in ase_lexicon.glob("*.pose"):
        # Extract the letter from the filename (approximate)
        name = pose_file.stem
        # Most filenames are like: fs-sts[hash]
        ase_poses[name] = pose_file
    
    print(f"Found {len(ase_poses)} ASE pose files\n")
    
    # For simplicity, just copy a few representative poses
    # In reality, you'd want to use the extracted poses from videos
    
    ase_pose_files = list(ase_lexicon.glob("*.pose"))
    
    index_rows = []
    entries: list[WordEntry] = []
    for i, word in enumerate(target_words):
        src_pose = ase_pose_files[i % len(ase_pose_files)]
        entries.append(WordEntry(word=word, pose_file=src_pose))

    for entry in entries:
        word = entry.word
        src_pose = entry.pose_file
        dest_pose = lse_lexicon / f"lse-{word}.pose"
        
        print(f"Mapping: {word} -> {src_pose.name}")
        
        copy_pose_file(src_pose, dest_pose)
        
        # Read to get frame count
        with open(dest_pose, 'rb') as f:
            pose = Pose.read(f.read())
            end_ms = _duration_ms(pose)
        
        index_rows.append({
            "path": f"lse/lse-{word}.pose",
            "spoken_language": "es",
            "signed_language": "lse",
            "start": 0,
            "end": end_ms,
            "words": word,
            "glosses": word.upper(),
            "priority": 0
        })
    
    # Write index
    index_path = lse_lexicon.parent / "index.csv"
    with open(index_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "path", "spoken_language", "signed_language", "start", "end",
            "words", "glosses", "priority"
        ])
        writer.writeheader()
        writer.writerows(index_rows)
    
    print(f"\n✓ Created LSE lexicon with {len(index_rows)} words")
    print(f"  (Using ASE poses as temporary placeholder)")
    return 0


if __name__ == "__main__":
    exit(main())
