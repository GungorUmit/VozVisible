#!/usr/bin/env python3
"""Render a Pose object as a skeleton avatar video."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from pose_format import Pose
from pose_format.pose_visualizer import PoseVisualizer

logger = logging.getLogger(__name__)


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
    if _render_with_ffmpeg(frames, output_path, width, height, fps):
        logger.info("Rendered with ffmpeg: %s", output_path)
        return

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

    # If we reached here, OpenCV wrote the file. If ffmpeg is available, ensure
    # the container serves an H.264/AVC file for maximum browser compatibility.
    try:
        if shutil.which("ffmpeg"):
            _transcode_to_h264_if_needed(output_path)
    except Exception as e:
        logger.exception("Post-write transcode check failed: %s", e)


def _render_with_ffmpeg(frames, output_path: str, width: int, height: int, fps: float) -> bool:
    ffmpeg = "ffmpeg"
    if not shutil.which(ffmpeg):
        logger.debug("ffmpeg not found on PATH; falling back to OpenCV writer")
        return False

    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps}",
        "-i",
        "pipe:0",
        "-an",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]

    logger.debug("Running ffmpeg cmd: %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception as e:
        logger.exception("Failed to start ffmpeg: %s", e)
        return False

    try:
        assert proc.stdin is not None
        for frame in frames:
            if frame is None:
                continue
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))
            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        stderr = proc.stderr.read() if proc.stderr else b""
        code = proc.wait()
        if code != 0:
            logger.error("ffmpeg failed (code=%s): %s", code, stderr.decode(errors="ignore"))
        return code == 0
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        return False


def _transcode_to_h264_if_needed(path: str) -> None:
    """Check container file codec and transcode to H.264 if not already.

    This replaces the original file on success.
    """
    # Inspect file codec
    try:
        cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", path]
        codec = subprocess.check_output(cmd_probe).decode().strip()
    except Exception:
        logger.exception("ffprobe failed to inspect %s", path)
        return

    if codec in ("h264", "avc1"):
        logger.debug("File %s already h264 (codec=%s)", path, codec)
        return

    if not shutil.which("ffmpeg"):
        logger.debug("ffmpeg not available; cannot transcode %s", path)
        return

    fd, tmp = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart",
            tmp,
        ]
        logger.info("Transcoding %s -> %s", path, tmp)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode == 0:
            os.replace(tmp, path)
            logger.info("Transcode successful: %s", path)
        else:
            logger.error("Transcode failed for %s: %s", path, proc.stderr.decode(errors="ignore"))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
