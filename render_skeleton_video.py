#!/usr/bin/env python3
"""Render a Pose object as a skeleton avatar video."""

from __future__ import annotations

import cv2
from pose_format import Pose
from pose_format.pose_visualizer import PoseVisualizer


def render_skeleton_video(pose: Pose, output_path: str) -> None:
    """Render pose frames as a clean skeleton avatar video.

    Uses pose_format's PoseVisualizer to draw the landmarks and limbs on a
    plain white background, then writes the frames with OpenCV so we do not
    depend on vidgear.
    """
    visualizer = PoseVisualizer(pose)
    frames = visualizer.draw(background_color=(255, 255, 255))

    width = int(pose.header.dimensions.width)
    height = int(pose.header.dimensions.height)
    fps = float(pose.body.fps)
    writer = None
    last_error = None
    # Render builds often lack H.264, so try a few common OpenCV/FFmpeg codecs.
    for codec in ("avc1", "mp4v", "avc3", "XVID"):
        fourcc = cv2.VideoWriter_fourcc(*codec)
        candidate = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if candidate.isOpened():
            writer = candidate
            break
        last_error = codec
        candidate.release()

    if writer is None:
        raise RuntimeError(f"Could not open video writer for {output_path} using codecs avc1/mp4v/avc3/XVID (last tried: {last_error})")

    try:
        for frame in frames:
            if frame is None:
                continue
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))
            # PoseVisualizer outputs RGB-style arrays; OpenCV expects BGR.
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()
