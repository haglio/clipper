from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np

from .loop_modes import (
    LOOP_MODE_BASE_TIP,
    LOOP_MODE_BASE_TIP_BASE,
    LOOP_MODE_TIP_BASE,
    LOOP_MODE_TIP_BASE_TIP,
)


def smoothstep01(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def ease_cos01(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def blend_pair(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    out = (1.0 - t) * a.astype(np.float32) + t * b.astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)


def flow_for_pair(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a_gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    flow_ab = cv2.calcOpticalFlowFarneback(
        a_gray, b_gray, None,
        pyr_scale=0.5, levels=3, winsize=25,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
    )
    flow_ba = cv2.calcOpticalFlowFarneback(
        b_gray, a_gray, None,
        pyr_scale=0.5, levels=3, winsize=25,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
    )
    return flow_ab, flow_ba


def remap_with_flow(img: np.ndarray, flow: np.ndarray, factor: float) -> np.ndarray:
    h, w = img.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    map_x = grid_x - factor * flow[..., 0]
    map_y = grid_y - factor * flow[..., 1]
    return cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )


def build_bridge(last_frame: np.ndarray, first_frame: np.ndarray, bridge_frames: int, mode: str) -> list[np.ndarray]:
    if bridge_frames <= 0:
        return []
    bridge = []

    if mode == "flow":
        flow_ab, flow_ba = flow_for_pair(last_frame, first_frame)

    for i in range(bridge_frames):
        t = (i + 1) / (bridge_frames + 1)
        t_eased = ease_cos01(t)
        if mode == "flow":
            a_warp = remap_with_flow(last_frame, flow_ab, t_eased)
            b_warp = remap_with_flow(first_frame, flow_ba, 1.0 - t_eased)
            frame = blend_pair(a_warp, b_warp, t_eased)
        else:
            frame = blend_pair(last_frame, first_frame, t_eased)
        bridge.append(frame)

    return bridge


def build_symmetric_blend(frames: list[np.ndarray], seam_frames: int) -> list[np.ndarray]:
    n = len(frames)
    out = [frame.copy() for frame in frames]
    for i in range(seam_frames):
        t = smoothstep01((i + 1) / seam_frames)
        start_idx = i
        end_idx = n - seam_frames + i
        start_f = frames[start_idx]
        end_f = frames[end_idx]
        midpoint = blend_pair(end_f, start_f, 0.5)
        out[start_idx] = blend_pair(start_f, midpoint, t)
        out[end_idx] = blend_pair(end_f, midpoint, t)
    return out


def decompose_similarity(M: np.ndarray, center: tuple[float, float]) -> tuple[float, float, float, float]:
    cos_a = M[0, 0]
    sin_a = M[1, 0]
    scale = math.sqrt(cos_a ** 2 + sin_a ** 2)
    angle = math.atan2(sin_a, cos_a)
    cx, cy = center
    tx = M[0, 2] - (cx - cos_a * cx + sin_a * cy)
    ty = M[1, 2] - (cy - sin_a * cx - cos_a * cy)
    return tx, ty, angle, scale


def compose_similarity(tx: float, ty: float, angle: float, scale: float, center: tuple[float, float]) -> np.ndarray:
    cx, cy = center
    cos_a = math.cos(angle) * scale
    sin_a = math.sin(angle) * scale
    M = np.array([
        [cos_a, -sin_a, cx - cos_a * cx + sin_a * cy + tx],
        [sin_a,  cos_a, cy - sin_a * cx - cos_a * cy + ty],
    ], dtype=np.float64)
    return M


def fractional_similarity(M: np.ndarray, t: float, center: tuple[float, float]) -> np.ndarray:
    tx, ty, angle, scale = decompose_similarity(M, center)
    log_scale = math.log(scale) if scale > 0 else 0.0
    return compose_similarity(tx * t, ty * t, angle * t, math.exp(log_scale * t), center)


def warp_affine(frame: np.ndarray, M: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    return cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def estimate_alignment(frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[np.ndarray | None, float]:
    h, w = frame_a.shape[:2]
    if h < 16 or w < 16:
        return None, 0.0
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=2000)
    try:
        kp_a, desc_a = orb.detectAndCompute(gray_a, None)
        kp_b, desc_b = orb.detectAndCompute(gray_b, None)
    except cv2.error:
        return None, 0.0
    if desc_a is None or desc_b is None or len(kp_a) < 8 or len(kp_b) < 8:
        return None, 0.0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = bf.knnMatch(desc_a, desc_b, k=2)
    good = []
    for m_pair in raw_matches:
        if len(m_pair) == 2 and m_pair[0].distance < 0.75 * m_pair[1].distance:
            good.append(m_pair[0])
    if len(good) < 8:
        return None, 0.0
    pts_a = np.array([kp_a[m.queryIdx].pt for m in good], dtype=np.float32)
    pts_b = np.array([kp_b[m.trainIdx].pt for m in good], dtype=np.float32)
    M, inliers = cv2.estimateAffinePartial2D(pts_a, pts_b, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None or inliers is None:
        return None, 0.0
    inlier_ratio = float(inliers.sum()) / len(good)
    if inlier_ratio < 0.3:
        return None, inlier_ratio
    return M, inlier_ratio


def build_registered_seam(
    frames: list[np.ndarray], seam_frames: int
) -> tuple[list[np.ndarray], bool]:
    n = len(frames)
    if n < 2 or seam_frames < 1:
        return frames, False

    M, inlier_ratio = estimate_alignment(frames[-1], frames[0])
    if M is None:
        return frames, False

    h, w = frames[0].shape[:2]
    center = (w / 2.0, h / 2.0)

    out = [frame.copy() for frame in frames]

    # Distribute the geometric correction across ALL frames so no single
    # transition has a perceptible shift.  Frame 0 stays at identity;
    # each subsequent frame is warped by an increasing fraction of M.
    for i in range(1, n):
        t = i / n
        warp_M = fractional_similarity(M, t, center)
        out[i] = warp_affine(out[i], warp_M)

    return out, True


def _find_rife_exe(project_root: str | None = None) -> str | None:
    """Locate the rife-ncnn-vulkan executable relative to the project root.

    ``project_root`` defaults to the checkout this module lives in; a caller
    passes one so the lookup can be exercised against a directory it controls.
    """
    if project_root is None:
        # Walk up from this file to find the project root (contains tools/)
        here = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(here)
    candidates = [
        os.path.join(project_root, "tools", "rife-ncnn-vulkan-20221029-windows", "rife-ncnn-vulkan.exe"),
        shutil.which("rife-ncnn-vulkan"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _rife_setup() -> tuple[str, str] | None:
    """Return (rife_exe, model_dir) or None if RIFE is unavailable."""
    rife_exe = _find_rife_exe()
    if rife_exe is None:
        return None
    model_dir = os.path.join(os.path.dirname(rife_exe), "rife-v4.6")
    if not os.path.isdir(model_dir):
        return None
    return rife_exe, model_dir


def _rife_interpolate_frame(
    rife_exe: str,
    model_dir: str,
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    timestep: float,
    tmpdir: str,
    tag: str = "0",
) -> np.ndarray | None:
    """Call RIFE to generate one interpolated frame at *timestep* between a and b."""
    input0 = os.path.join(tmpdir, f"in0_{tag}.png")
    input1 = os.path.join(tmpdir, f"in1_{tag}.png")
    out_path = os.path.join(tmpdir, f"out_{tag}.png")
    cv2.imwrite(input0, frame_a)
    cv2.imwrite(input1, frame_b)
    cmd = [
        rife_exe, "-0", input0, "-1", input1, "-o", out_path,
        "-s", str(timestep), "-m", model_dir,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    frame = cv2.imread(out_path, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    h, w = frame_a.shape[:2]
    if frame.shape[:2] != (h, w):
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
    return frame


def build_rife_bridge(
    last_frame: np.ndarray, first_frame: np.ndarray, bridge_frames: int
) -> list[np.ndarray] | None:
    """Generate bridge frames using RIFE neural frame interpolation."""
    if bridge_frames <= 0:
        return None
    setup = _rife_setup()
    if setup is None:
        return None
    rife_exe, model_dir = setup

    tmpdir = tempfile.mkdtemp(prefix="rife_bridge_")
    try:
        results: list[np.ndarray] = []
        for i in range(bridge_frames):
            t = (i + 1) / (bridge_frames + 1)
            frame = _rife_interpolate_frame(
                rife_exe, model_dir, last_frame, first_frame, t, tmpdir, tag=f"b{i}"
            )
            if frame is None:
                return None
            results.append(frame)
        return results
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_rife_seam(
    frames: list[np.ndarray], seam_frames: int
) -> list[np.ndarray] | None:
    """Gradually converge frames near the seam using RIFE interpolation.

    For each pair (frames[N-i], frames[i-1]), generates RIFE-interpolated
    versions that subtly shift each toward its partner.  Influence is highest
    at the seam and fades to zero at the edges.  Every modified frame is a
    single RIFE output — no alpha compositing.

    Returns the modified frame list, or None if RIFE is unavailable.
    """
    n = len(frames)
    if seam_frames <= 0 or n < 4:
        return None
    # Ensure we don't overlap the two sides (each pair uses one from each side)
    seam_frames = min(seam_frames, n // 2)
    setup = _rife_setup()
    if setup is None:
        return None
    rife_exe, model_dir = setup

    out = list(frames)  # shallow copy; we replace individual elements
    tmpdir = tempfile.mkdtemp(prefix="rife_seam_")
    try:
        for i in range(1, seam_frames + 1):
            tail_idx = n - i
            head_idx = i - 1
            # Influence: 1.0 nearest the seam, fading toward 0.0 at the edge
            influence = smoothstep01((seam_frames - i + 1) / seam_frames)
            timestep = influence * 0.5  # max halfway toward partner
            if timestep < 0.02:
                continue

            new_tail = _rife_interpolate_frame(
                rife_exe, model_dir,
                frames[tail_idx], frames[head_idx],
                timestep, tmpdir, tag=f"t{i}",
            )
            if new_tail is None:
                return None
            out[tail_idx] = new_tail

            new_head = _rife_interpolate_frame(
                rife_exe, model_dir,
                frames[head_idx], frames[tail_idx],
                timestep, tmpdir, tag=f"h{i}",
            )
            if new_head is None:
                return None
            out[head_idx] = new_head

        return out
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def resize_frames(frames: list[np.ndarray], scale: float) -> list[np.ndarray]:
    if scale >= 0.999:
        return frames

    h, w = frames[0].shape[:2]
    new_w = max(2, int(round(w * scale)))
    new_h = max(2, int(round(h * scale)))

    if new_w % 2:
        new_w -= 1
    if new_h % 2:
        new_h -= 1

    return [cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA) for frame in frames]


def shift_frames_halfway(frames: list[np.ndarray]) -> list[np.ndarray]:
    if len(frames) < 2:
        return list(frames)
    shift = max(1, len(frames) // 2)
    return list(frames[shift:]) + list(frames[:shift])


def normalize_loop_mode(frames: list[np.ndarray], loop_mode: str) -> list[np.ndarray]:
    if loop_mode == LOOP_MODE_BASE_TIP_BASE:
        return [frame.copy() for frame in frames]
    if loop_mode == LOOP_MODE_TIP_BASE_TIP:
        return [frame.copy() for frame in shift_frames_halfway(frames)]
    if loop_mode == LOOP_MODE_BASE_TIP:
        return [frame.copy() for frame in frames] + [frame.copy() for frame in frames[-2::-1]]
    if loop_mode == LOOP_MODE_TIP_BASE:
        reversed_frames = list(reversed(frames))
        return [frame.copy() for frame in reversed_frames[:-1]] + [frame.copy() for frame in frames]
    raise RuntimeError(f"Unsupported loop mode: {loop_mode}")
