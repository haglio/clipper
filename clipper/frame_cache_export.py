from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np

MAX_CACHE_MB = 50.0
_MIN_QUALITY = 10
_QUALITY_STEP = 5


def _encode_frames(bgr_frames: list[np.ndarray], quality: int) -> list[bytes]:
    encoded: list[bytes] = []
    for bgr in bgr_frames:
        ok, buf = cv2.imencode(".webp", bgr, [cv2.IMWRITE_WEBP_QUALITY, quality])
        if not ok:
            raise RuntimeError(f"WebP encode failed at frame {len(encoded)}")
        encoded.append(buf.tobytes())
    return encoded


def generate_frame_cache(
    video_path: Path, cache_path: Path, *, quality: int = 95, max_mb: float = MAX_CACHE_MB
) -> None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    bgr_frames: list[np.ndarray] = []
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            bgr_frames.append(bgr)
    finally:
        cap.release()

    if not bgr_frames:
        raise RuntimeError(f"No frames decoded from: {video_path}")

    max_bytes = int(max_mb * 1024 * 1024)
    current_quality = quality

    while True:
        frames_data = _encode_frames(bgr_frames, current_quality)
        total_data = sum(len(b) for b in frames_data)
        if total_data <= max_bytes or current_quality <= _MIN_QUALITY:
            break
        current_quality = max(_MIN_QUALITY, current_quality - _QUALITY_STEP)

    meta = {
        "width": width,
        "height": height,
        "frame_count": len(frames_data),
        "source": video_path.name,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(cache_path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("meta.json", json.dumps(meta))
        for i, buf in enumerate(frames_data):
            zf.writestr(f"frames/{i:06d}.webp", buf)
