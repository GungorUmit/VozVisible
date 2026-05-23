#!/usr/bin/env python3
"""Create a custom LSE lexicon from word videos."""

import argparse
import csv
import cv2
import numpy as np
from pathlib import Path
import io
from pose_format import Pose
from pose_format.numpy import NumPyPoseBody


def get_reference_pose_header():
    """Load reference header from an existing pose file."""
    ref_file = Path("spoken_to_signed/assets/fingerspelling_lexicon/ase/fs-stse28e9ac023b0e29ca0a3acc12dc46540.pose")
    if ref_file.exists():
        with open(ref_file, 'rb') as f:
            pose = Pose.read(f.read())
            return pose.header
    return None


def create_placeholder_pose(video_path: Path) -> Pose:
    """Create placeholder pose from video metadata."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    header = get_reference_pose_header()
    if header is None:
        return None
    
    # 586 keypoints from reference analysis
    num_keypoints = 586
    
    data = np.zeros((frame_count, 1, num_keypoints, 3), dtype=np.float32)
    
    for frame_idx in range(frame_count):
        for keypoint_idx in range(num_keypoints):
            x = 0.3 + (keypoint_idx % 100) * 0.007
            y = 0.3 + (keypoint_idx // 100) * 0.1
            z = 0.0
            data[frame_idx, 0, keypoint_idx, :] = [x, y, z]
    
    confidence = np.full((frame_count, 1, num_keypoints), 0.5, dtype=np.float32)
    
    pose_body = NumPyPoseBody(fps=fps, data=data, confidence=confidence)
    pose = Pose(header, pose_body)
    
    return pose


def main():
    parser = argparse.ArgumentParser(description="Create LSE lexicon from word videos")
    parser.add_argument("--input-dir", default="spoken_to_signed/videos_lse")
    parser.add_argument("--output-lexicon", default="spoken_to_signed/assets/lse_lexicon")
    parser.add_argument("--spoken-language", default="es")
    parser.add_argument("--signed-language", default="lse")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_lexicon = Path(args.output_lexicon)
    poses_dir = output_lexicon / args.signed_language
    
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        return 1
    
    poses_dir.mkdir(parents=True, exist_ok=True)
    
    video_files = sorted(list(input_dir.glob("*.mp4")) + list(input_dir.glob("*.mov")))
    if not video_files:
        print(f"✗ No video files found")
        return 1
    
    print(f"\nCreating LSE lexicon from {len(video_files)} videos...\n")
    
    index_rows = []
    
    for video_path in video_files:
        word = video_path.stem
        gloss = word.upper()
        
        print(f"Processing: {word}")
        
        try:
            pose = create_placeholder_pose(video_path)
            
            if pose is None:
                print(f"  ✗ Failed\n")
                continue
            
            pose_filename = f"lse-{word}.pose"
            pose_path = poses_dir / pose_filename
            
            with open(pose_path, 'wb') as f:
                buffer = io.BytesIO()
                pose.write(buffer)
                f.write(buffer.getvalue())
            
            num_frames = len(pose.body.data)
            
            index_rows.append({
                "path": f"{args.signed_language}/{pose_filename}",
                "spoken_language": args.spoken_language,
                "signed_language": args.signed_language,
                "start": 0,
                "end": num_frames - 1,
                "words": word,
                "glosses": gloss,
                "priority": 0
            })
            
            print(f"  ✓ Created ({num_frames} frames)\n")
            
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            continue
    
    if index_rows:
        index_path = output_lexicon / "index.csv"
        with open(index_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "path", "spoken_language", "signed_language", "start", "end", 
                "words", "glosses", "priority"
            ])
            writer.writeheader()
            writer.writerows(index_rows)
        
        print(f"✓ Lexicon created with {len(index_rows)} words")
        print(f"✓ Location: {index_path}")
        print(f"\nUsage:")
        print(f"  python generate_video.py --text 'tu frase' \\")
        print(f"    --lexicon {output_lexicon} --signed-language {args.signed_language}")
        return 0
    else:
        print(f"✗ No poses created")
        return 1


if __name__ == "__main__":
    exit(main())
