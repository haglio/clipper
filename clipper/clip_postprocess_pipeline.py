from __future__ import annotations

import logging
import os
from collections.abc import Callable

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
from .postprocess_options import PostprocessOptions

logger = logging.getLogger(__name__)

# How far along each finished step leaves the run. Coarse, and true at the
# moment it is said: the step it names has completed. Finer would mean knowing
# the total work, which nothing here does -- and a bar invented to look finer
# than that is what these replaced. The values are roughly what decoding and
# building the frames cost against the encode, on a clip the length clipper
# exports. Nothing says 1.0: returning is what says the run is over.
_DECODED = 0.2
_FRAMES_BUILT = 0.6


def _nobody_listening(_fraction: float) -> None:
    """What the progress goes to when the run was started by hand."""


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


def _softly_blended(work_frames: list, symmetric_blend: int, normalized_n: int) -> list:
    """Pull the first and last frames toward each other, if --symmetric-blend asked.

    The width is the flag, capped at a quarter of the clip.  Both bridge paths
    below reach this, which is why it is not written out twice.
    """
    if symmetric_blend <= 0:
        return work_frames
    blend_frames = min(symmetric_blend, max(1, normalized_n // 4))
    return build_symmetric_blend(work_frames, blend_frames)


def _with_bridge(work_frames: list, bridge: list, bridge_frames: int, keep_length: bool) -> list:
    """The clip with the bridge on the end: in place of the tail, or after it."""
    if not keep_length:
        return work_frames + bridge
    if bridge_frames >= len(work_frames):
        raise RuntimeError("--keep-length bridge is too long for this clip.")
    return work_frames[:-bridge_frames] + bridge


def _registered_seam(
    work_frames: list,
    *,
    bridge_frames: int,
    keep_length: bool,
    symmetric_blend: int,
    seam_frames: int,
) -> list | None:
    """The finished clip a keypoint-aligned seam gives, or None when the ends
    could not be aligned and the caller should bridge them instead.

    ``build_registered_seam`` hands the frames straight back when it cannot
    align them, so the caller's list is untouched on the None.
    """
    normalized_n = len(work_frames)
    seam_region = min(
        symmetric_blend if symmetric_blend > 0 else max(1, normalized_n // 3),
        max(1, normalized_n // 3),
    )
    registered, registered_ok = build_registered_seam(work_frames, seam_region)
    if not registered_ok:
        return None

    if seam_frames > 0:
        # Nudge the frames either side of the seam together; where that
        # converges it handles the transition and no bridge is wanted.
        converged = build_rife_seam(registered, seam_frames)
        if converged is not None:
            return list(converged)

    rife_bridge = build_rife_bridge(registered[-1], registered[0], bridge_frames)
    if rife_bridge is None:
        # No interpolator on this machine: the geometric correction stands alone.
        return list(registered)
    return _with_bridge(registered, rife_bridge, bridge_frames, keep_length)


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
        registered = _registered_seam(
            work_frames,
            bridge_frames=bridge_frames,
            keep_length=keep_length,
            symmetric_blend=symmetric_blend,
            seam_frames=seam_frames,
        )
        if registered is not None:
            return registered, normalized_n
        bridge_mode = "flow"
    else:
        # seam_frames is not read here: --seam-ms drives RIFE seam convergence,
        # which only the register path runs.  The blend width comes from
        # --symmetric-blend, and reusing the parameter's name for it hid that.
        bridge_mode = mode

    work_frames = _softly_blended(work_frames, symmetric_blend, normalized_n)
    bridge = build_bridge(work_frames[-1], work_frames[0], bridge_frames, bridge_mode)
    return _with_bridge(work_frames, bridge, bridge_frames, keep_length), normalized_n


def postprocess_clip(
    options: PostprocessOptions,
    report: Callable[[float], None] | None = None,
) -> dict[str, int | float | str]:
    say = report or _nobody_listening
    if options.max_mb <= 0:
        raise RuntimeError("--max-mb must be greater than 0.")

    max_output_size_bytes = int(options.max_mb * 1024 * 1024)
    meta = ffprobe_video(options.input)
    fps = meta["fps"]

    frames = read_frames(options.input)
    input_count = len(frames)
    if input_count < 3:
        raise RuntimeError("Clip is too short.")
    say(_DECODED)

    normalized_preview = normalize_loop_mode(frames, options.loop_mode)
    bridge_frames = compute_bridge_frames(
        fps=fps,
        bridge_ms=options.bridge_ms,
        bridge_frames=options.bridge_frames,
        normalized_frame_count=len(normalized_preview),
    )
    seam_frames_count = compute_seam_frames(
        fps=fps,
        seam_ms=options.seam_ms,
        normalized_frame_count=len(normalized_preview),
    )
    out_frames, normalized_n = build_output_frames(
        frames,
        loop_mode=options.loop_mode,
        bridge_frames=bridge_frames,
        mode=options.mode,
        keep_length=options.keep_length,
        symmetric_blend=options.symmetric_blend,
        seam_frames=seam_frames_count,
    )
    say(_FRAMES_BUILT)

    scale = 1.0
    min_dim = 64
    attempt = 0
    while True:
        attempt += 1
        frames_to_encode = resize_frames(out_frames, scale)
        encode_with_ffmpeg(
            frames_to_encode,
            fps,
            options.output,
            options.crf,
            options.preset,
            options.pix_fmt,
            input_audio_path=options.input if options.copy_audio else None,
        )

        size_bytes = os.path.getsize(options.output)
        if size_bytes <= max_output_size_bytes:
            break

        h, w = frames_to_encode[0].shape[:2]
        if min(h, w) <= min_dim:
            logger.warning(
                "Output is still >%g MB at the minimum allowed resolution.",
                options.max_mb,
            )
            break

        scale *= 0.9

    final_size = os.path.getsize(options.output)
    return {
        "fps": fps,
        "input_frames": input_count,
        "loop_mode": options.loop_mode,
        "normalized_frames": normalized_n,
        "bridge_frames": bridge_frames,
        "output_frames": len(out_frames),
        "encode_attempts": attempt,
        "final_scale": scale,
        "final_size_bytes": final_size,
        "target_max_mb": options.max_mb,
        "output_path": options.output,
    }
