from __future__ import annotations

import os
import subprocess
from pathlib import Path

import cv2

TOPAZ_FFMPEG = Path(r"C:\Program Files\Topaz Labs LLC\Topaz Video\ffmpeg.exe")
TVAI_MODEL_DIR = Path(r"C:\ProgramData\Topaz Labs LLC\Topaz Video\models")

TARGET_FRAMES = 240
MAX_OUTPUT_MB = 50.0


def topaz_available() -> bool:
    return TOPAZ_FFMPEG.is_file() and TVAI_MODEL_DIR.is_dir()


def _probe_clip(path: Path) -> tuple[int, float, int, int]:
    """Return (frame_count, duration_seconds, width, height)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    duration = total / fps if fps > 0 else 0
    return total, duration, w, h


def _compute_upscale_factor(
    w: int, h: int, target_frames: int, duration: float, max_mb: float
) -> int:
    """Pick the largest integer scale (1-4) whose output stays under max_mb."""
    target_fps = target_frames / duration if duration > 0 else 60
    for scale in (4, 3, 2, 1):
        out_w, out_h = w * scale, h * scale
        # Conservative estimate: WebP at quality 95 ~= 0.5 bytes/pixel
        estimated_cache_mb = (out_w * out_h * 0.5 * target_frames) / (1024 * 1024)
        # H.265 video is much smaller, so MB cap is generous; check RAM instead
        estimated_ram_mb = (out_w * out_h * 3 * target_frames) / (1024 * 1024)
        if estimated_cache_mb <= max_mb and estimated_ram_mb <= 2000:
            return scale
    return 1


def enhance_clip(
    input_path: Path,
    output_path: Path,
    *,
    target_frames: int = TARGET_FRAMES,
    max_mb: float = MAX_OUTPUT_MB,
) -> dict:
    """Run Topaz Video AI frame interpolation + upscaling on a clip."""
    if not topaz_available():
        raise RuntimeError("Topaz Video AI not found")

    frame_count, duration, w, h = _probe_clip(input_path)
    if duration <= 0:
        raise RuntimeError(f"Clip has zero duration: {input_path}")

    target_fps = target_frames / duration
    scale = _compute_upscale_factor(w, h, target_frames, duration, max_mb)

    filter_complex = (
        f"tvai_fi=model=apo-8:slowmo=1:fps={target_fps:.4f}:rdt=0.01:device=0:vram=1:instances=1,"
        f"tvai_up=model=gcg-5:scale={scale}:device=0:vram=1:instances=1"
    )

    env = os.environ.copy()
    env["TVAI_MODEL_DIR"] = str(TVAI_MODEL_DIR)
    env["TVAI_MODEL_DATA_DIR"] = str(TVAI_MODEL_DIR)

    cmd = [
        str(TOPAZ_FFMPEG),
        "-hide_banner", "-nostdin", "-y",
        "-strict", "2",
        "-hwaccel", "cuda",
        "-i", str(input_path),
        "-sws_flags", "spline+accurate_rnd+full_chroma_int",
        "-filter_complex", filter_complex,
        "-c:v", "hevc_nvenc",
        "-profile:v", "main",
        "-pix_fmt", "yuv420p",
        "-b_ref_mode", "disabled",
        "-tag:v", "hvc1",
        "-g", "30",
        "-preset", "p7",
        "-tune", "hq",
        "-rc", "constqp",
        "-qp", "17",
        "-rc-lookahead", "20",
        "-spatial_aq", "1",
        "-aq-strength", "15",
        "-b:v", "0",
        "-an",
        "-fps_mode:v", "cfr",
        "-bf", "0",
        "-f", "mp4",
        str(output_path),
    ]

    result = subprocess.run(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"Topaz enhance failed:\n{stderr}")

    out_count, out_duration, out_w, out_h = _probe_clip(output_path)
    final_mb = output_path.stat().st_size / (1024 * 1024)

    return {
        "input_frames": frame_count,
        "input_resolution": f"{w}x{h}",
        "output_frames": out_count,
        "output_resolution": f"{out_w}x{out_h}",
        "scale": scale,
        "target_fps": target_fps,
        "final_mb": final_mb,
    }
