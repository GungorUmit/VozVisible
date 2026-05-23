#!/usr/bin/env python3
"""Extract pose files from word videos in videos_lse/ folder.

Creates a custom lexicon with Spanish word → pose mappings.
"""

import argparse
import csv
import subprocess
from pathlib import Path
from typing import Optional

from pose_format import Pose


def extract_pose_from_video(video_path: Path, pose_path: Path) -> bool:
    """Extract pose from video using pose_format CLI with fallback methods.
    
    Args:
        video_path: Path to input video (.mp4, .mov, etc.)
        pose_path: Path where .pose file will be saved
        
    Returns:
        True if successful, False otherwise
    """
    pose_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Try method 1: Use pose_format's pose_format_convert CLI if available
    try:
        result = subprocess.run(
            ["pose_format_convert", str(video_path), str(pose_path), "--format", "mediapipe"],
            capture_output=True,
            timeout=60
        )
        if result.returncode == 0:
            print(f"✓ Extracted pose from {video_path.name} using pose_format_convert")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        print(f"  pose_format_convert failed: {e}")
    
    # Try method 2: Use ffmpeg + custom mediapipe script
    try:
        # Create a minimal pose file from keyframe
        # This is a fallback that extracts a static pose from the first frame
        result = subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-vf", "fps=1", "-frames:v", "1", "/tmp/frame.png"],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"  Extracted frame from {video_path.name}")
            # Now use mediapipe to detect pose from this frame
            # This would require additional setup
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print(f"✗ Failed to extract pose from {video_path.name}")
    return False


def create_pose_file_from_video(video_path: Path, output_pose_path: Path) -> bool:
    """Create a simple pose file from video using an alternative approach.
    
    This method uses OpenCV to read the video and creates a basic pose structure.
    """
    try:
        import cv2
        import json
        import numpy as np
    except ImportError:
        print("OpenCV not available, skipping video processing")
        return False
    
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  Could not open video: {video_path}")
            return False
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"  Video info: {frame_count} frames @ {fps} fps")
        
        # For now, create a placeholder pose file
        # In production, you'd extract keypoints from each frame using MediaPipe
        # But for the lexicon, we can use the first frame as representative
        
        cap.release()
        
        # Create a minimal valid pose file structure
        # Using pose_format's schema
        pose_data = {
            "version": 1.0,
            "body": {
                "keypoints": [],  # Would contain actual keypoints
                "fps": fps,
            }
        }
        
        output_pose_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_pose_path, 'w') as f:
            json.dump(pose_data, f)
        
        print(f"✓ Created pose file: {output_pose_path.name} ({frame_count} frames @ {fps} fps)")
        return True
        
    except Exception as e:
        print(f"✗ Error processing {video_path.name}: {e}")
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract poses from word videos and create a custom lexicon"
    )
    parser.add_argument(
        "--input-dir",
        default="spoken_to_signed/videos_lse",
        help="Directory containing word videos"
    )
    parser.add_argument(
        "--output-lexicon",
        default="spoken_to_signed/assets/lse_lexicon",
        help="Output directory for poses and index.csv"
    )
    parser.add_argument(
        "--spoken-language",
        default="es",
        help="Spoken language code (es for Spanish)"
    )
    parser.add_argument(
        "--signed-language",
        default="lse",
        help="Signed language code (lse for Lengua de Signos Española)"
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional CSV with columns: word,video,gloss"
    )
    return parser


def load_manifest(input_dir: Path, manifest_path: Optional[Path] = None) -> list[dict]:
    """Load word-to-video mapping from manifest or infer from filenames."""
    entries = []
    
    if manifest_path and manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(row)
    else:
        # Infer from video filenames
        for video in sorted(input_dir.glob("*.[mM][pP]4")):
            word = video.stem
            entries.append({
                "word": word,
                "video": video.name,
                "gloss": word.upper()
            })
    
    return entries


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    
    input_dir = Path(args.input_dir)
    output_lexicon = Path(args.output_lexicon)
    
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        return 1
    
    print(f"\nExtracting poses from videos in: {input_dir}")
    print(f"Output lexicon: {output_lexicon}\n")
    
    # Load manifest
    manifest_path = Path(args.manifest) if args.manifest else input_dir / "manifest.csv"
    entries = load_manifest(input_dir, manifest_path if manifest_path.exists() else None)
    
    if not entries:
        print("✗ No entries found in manifest or inferred from video files")
        return 1
    
    # Create output structure
    poses_dir = output_lexicon / args.signed_language
    poses_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract poses
    index_rows = []
    for entry in entries:
        word = entry.get("word", "").strip()
        video_name = entry.get("video", "").strip()
        gloss = entry.get("gloss", word).upper()
        
        if not word or not video_name:
            print(f"⚠ Skipping entry with missing word or video: {entry}")
            continue
        
        video_path = input_dir / video_name
        if not video_path.exists():
            print(f"⚠ Video not found: {video_path}")
            continue
        
        print(f"Processing: {word} ({video_name})")
        
        # Create pose filename
        pose_filename = f"lse-{word}.pose"
        pose_path = poses_dir / pose_filename
        
        # Try to extract pose
        success = extract_pose_from_video(video_path, pose_path)
        
        if success and pose_path.exists():
            # Get pose duration
            try:
                with open(pose_path, 'rb') as f:
                    pose = Pose.read(f.read())
                    duration = len(pose.body.data) / pose.body.fps if hasattr(pose.body, 'fps') else 0
                    start_frame = 0
                    end_frame = len(pose.body.data) - 1 if hasattr(pose.body, 'data') else 0
            except:
                duration = 0
                start_frame = 0
                end_frame = 0
            
            index_rows.append({
                "path": str(pose_path.relative_to(output_lexicon)),
                "spoken_language": args.spoken_language,
                "signed_language": args.signed_language,
                "start": start_frame,
                "end": end_frame,
                "words": word,
                "glosses": gloss,
                "priority": 0
            })
            print(f"  ✓ Added to lexicon: {word} → {gloss}")
        else:
            print(f"  ✗ Could not extract pose from {video_name}")
    
    # Write index.csv
    index_path = output_lexicon / "index.csv"
    if index_rows:
        with open(index_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "path", "spoken_language", "signed_language", "start", "end", "words", "glosses", "priority"
            ])
            writer.writeheader()
            writer.writerows(index_rows)
        
        print(f"\n✓ Created lexicon index: {index_path}")
        print(f"  {len(index_rows)} entries written")
        return 0
    else:
        print(f"\n✗ No poses were successfully extracted")
        return 1


if __name__ == "__main__":
    exit(main())
