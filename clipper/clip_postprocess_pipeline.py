from __future__ import annotations

import os
from typing import Any

from .clip_postprocess_media import encode_with_ffmpeg, ffprobe_video, read_frames
from .clip_postprocess_transforms import (
    build_bridge,
    build_registered_seam,
    build_rife_bridge,
    build_rife_seam,
    build_symmetric_blend,
    normalize_loop_mode,
    resize_frames,
)


def compute_bridge_frames(*, fps: float, bridge_ms: float, bridge_frames: int | None, normalized_frame_count: int) -> int:
    frames = bridge_frames
    if frames is None:
        frames = max(1, int(round(fps * (bridge_ms / 1000.0))))
    max_bridge = max(1, normalized_frame_count // 3)
    return max(1, min(frames, max_bridge))


def compute_seam_frames(*, fps: float, seam_ms: float, normalized_frame_count: int) -> int:
    if seam_ms <= 0:
        return 0
    frames = max(0, int(round(fps * (seam_ms / 1000.0))))
    return min(frames, normalized_frame_count // 3)


def build_output_frames(
    frames: list,
    *,
    loop_mode: str,
    bridge_frames: int,
    mode: str,
    keep_length: bool,
    symmetric_blend: int,
    seam_frames: int = 0,
) -> tuple[list, int]:
    work_frames = normalize_loop_mode(frames, loop_mode)
    normalized_n = len(work_frames)

    if mode == "register":
        seam_region = min(
            symmetric_blend if symmetric_blend > 0 else max(1, normalized_n // 3),
            max(1, normalized_n // 3),
        )
        work_frames, registered_ok = build_registered_seam(
            work_frames, seam_region
        )
        if registered_ok:
            # RIFE seam convergence: gradually nudge frames near the seam
            if seam_frames > 0:
                converged = build_rife_seam(work_frames, seam_frames)
                if converged is not None:
                    # Seam convergence handles the transition; no bridge needed.
                    return list(converged), normalized_n
            # No seam convergence — try short RIFE bridge at the seam point
            rife_bridge = build_rife_bridge(
                work_frames[-1], work_frames[0], bridge_frames
            )
            if rife_bridge is not None:
                if keep_length:
                    if bridge_frames >= len(work_frames):
                        raise RuntimeError(
                            "--keep-length bridge is too long for this clip."
                        )
                    return work_frames[:-bridge_frames] + rife_bridge, normalized_n
                return work_frames + rife_bridge, normalized_n
            # RIFE unavailable — geometric-only (no bridge)
            return list(work_frames), normalized_n
        # Fallback to existing approach
        if symmetric_blend > 0:
            sf = min(symmetric_blend, max(1, normalized_n // 4))
            work_frames = build_symmetric_blend(work_frames, sf)
        bridge = build_bridge(work_frames[-1], work_frames[0], bridge_frames, "flow")
    else:
        if symmetric_blend > 0:
            seam_frames = min(symmetric_blend, max(1, normalized_n // 4))
            work_frames = build_symmetric_blend(work_frames, seam_frames)
        bridge = build_bridge(work_frames[-1], work_frames[0], bridge_frames, mode)

    if keep_length:
        if bridge_frames >= len(work_frames):
            raise RuntimeError("--keep-length bridge is too long for this clip.")
        return work_frames[:-bridge_frames] + bridge, normalized_n
    return work_frames + bridge, normalized_n


def postprocess_clip(args: Any) -> dict[str, int | float | str]:
    if args.max_mb <= 0:
        raise RuntimeError("--max-mb must be greater than 0.")

    max_output_size_bytes = int(args.max_mb * 1024 * 1024)
    meta = ffprobe_video(args.input)
    fps = meta["fps"]

    frames = read_frames(args.input)
    input_count = len(frames)
    if input_count < 3:
        raise RuntimeError("Clip is too short.")

    normalized_preview = normalize_loop_mode(frames, args.loop_mode)
    bridge_frames = compute_bridge_frames(
        fps=fps,
        bridge_ms=args.bridge_ms,
        bridge_frames=args.bridge_frames,
        normalized_frame_count=len(normalized_preview),
    )
    seam_frames_count = compute_seam_frames(
        fps=fps,
        seam_ms=getattr(args, "seam_ms", 250.0),
        normalized_frame_count=len(normalized_preview),
    )
    out_frames, normalized_n = build_output_frames(
        frames,
        loop_mode=args.loop_mode,
        bridge_frames=bridge_frames,
        mode=args.mode,
        keep_length=args.keep_length,
        symmetric_blend=args.symmetric_blend,
        seam_frames=seam_frames_count,
    )

    scale = 1.0
    min_dim = 64
    attempt = 0
    while True:
        attempt += 1
        frames_to_encode = resize_frames(out_frames, scale)
        encode_with_ffmpeg(
            frames_to_encode,
            fps,
            args.output,
            args.crf,
            args.preset,
            args.pix_fmt,
            input_audio_path=args.input if args.copy_audio else None,
        )

        size_bytes = os.path.getsize(args.output)
        if size_bytes <= max_output_size_bytes:
            break

        h, w = frames_to_encode[0].shape[:2]
        if min(h, w) <= min_dim:
            print(f"Warning: output is still >{args.max_mb:g} MB at minimum allowed resolution.")
            break

        scale *= 0.9

    final_size = os.path.getsize(args.output)
    return {
        "fps": fps,
        "input_frames": input_count,
        "loop_mode": args.loop_mode,
        "normalized_frames": normalized_n,
        "bridge_frames": bridge_frames,
        "output_frames": len(out_frames),
        "encode_attempts": attempt,
        "final_scale": scale,
        "final_size_bytes": final_size,
        "target_max_mb": args.max_mb,
        "output_path": args.output,
    }
