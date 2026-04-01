from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np


def generate_frame_cache(video_path: Path, cache_path: Path, *, quality: int = 95) -> None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frames_data: list[bytes] = []
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            ok, buf = cv2.imencode(".webp", bgr, [cv2.IMWRITE_WEBP_QUALITY, quality])
            if not ok:
                raise RuntimeError(f"WebP encode failed at frame {len(frames_data)}")
            frames_data.append(buf.tobytes())
    finally:
        cap.release()

    if not frames_data:
        raise RuntimeError(f"No frames decoded from: {video_path}")

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
