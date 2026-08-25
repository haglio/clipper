from __future__ import annotations

import pytest

from clipper.clip_postprocess_pipeline import build_output_frames, compute_bridge_frames


def test_compute_bridge_frames_uses_milliseconds_when_explicit_frames_missing():
    result = compute_bridge_frames(fps=20.0, bridge_ms=150.0, bridge_frames=None, normalized_frame_count=20)
    assert result == 3


def test_compute_bridge_frames_caps_to_one_third_of_normalized_frames():
    result = compute_bridge_frames(fps=60.0, bridge_ms=500.0, bridge_frames=None, normalized_frame_count=9)
    assert result == 3


def test_build_output_frames_keep_length_replaces_tail_with_bridge(frames_of, values_of):
    out_frames, normalized_n = build_output_frames(
        frames_of([1, 2, 3, 4]),
        loop_mode="base-tip-base",
        bridge_frames=1,
        mode="blend",
        keep_length=True,
        symmetric_blend=0,
    )
    assert normalized_n == 4
    assert len(out_frames) == 4
    assert values_of(out_frames[:3]) == [1, 2, 3]


def test_build_output_frames_append_keeps_original_and_adds_bridge(frames_of, values_of):
    out_frames, normalized_n = build_output_frames(
        frames_of([1, 2, 3, 4]),
        loop_mode="base-tip-base",
        bridge_frames=2,
        mode="blend",
        keep_length=False,
        symmetric_blend=0,
    )
    assert normalized_n == 4
    assert len(out_frames) == 6
    assert values_of(out_frames[:4]) == [1, 2, 3, 4]


def test_build_output_frames_register_mode_falls_back_on_tiny_frames(frames_of):
    """Register mode should fall back gracefully on 1x1 frames with no keypoints."""
    out_frames, normalized_n = build_output_frames(
        frames_of([10, 20, 30, 40, 50, 60]),
        loop_mode="base-tip-base",
        bridge_frames=1,
        mode="register",
        keep_length=True,
        symmetric_blend=0,
    )
    assert normalized_n == 6
    assert len(out_frames) == 6


def test_build_output_frames_rejects_keep_length_when_bridge_is_too_long(frames_of):
    with pytest.raises(RuntimeError, match="--keep-length bridge is too long"):
        build_output_frames(
            frames_of([1, 2, 3]),
            loop_mode="base-tip-base",
            bridge_frames=3,
            mode="blend",
            keep_length=True,
            symmetric_blend=0,
        )
