from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from clipper.clip_postprocess_pipeline import (
    build_output_frames,
    compute_bridge_frames,
    compute_seam_frames,
    postprocess_clip,
)


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


def test_compute_seam_frames_is_zero_when_seam_convergence_is_switched_off():
    assert compute_seam_frames(fps=30.0, seam_ms=0.0, normalized_frame_count=90) == 0


def test_compute_seam_frames_converts_milliseconds_at_the_clips_own_rate():
    assert compute_seam_frames(fps=30.0, seam_ms=250.0, normalized_frame_count=90) == 8


def test_compute_seam_frames_never_takes_more_than_a_third_of_the_clip():
    assert compute_seam_frames(fps=30.0, seam_ms=250.0, normalized_frame_count=9) == 3


# ---------------------------------------------------------------------------
# postprocess_clip, end to end with ffmpeg stubbed at the media boundary
# ---------------------------------------------------------------------------

class _RecordingEncoder:
    """Stands in for the ffmpeg pipe: writes a file of a chosen size, remembers
    everything it was handed.

    Only ``clip_postprocess_media``'s three I/O functions are stubbed; every
    frame the pipeline produces is produced for real.
    """

    def __init__(self, *sizes: int):
        self.sizes = list(sizes) or [16]
        self.calls: list[dict] = []

    def __call__(self, frames, fps, out_path, crf, preset, pix_fmt, input_audio_path=None):
        self.calls.append({
            "frame_count": len(frames),
            "shape": frames[0].shape[:2],
            "fps": fps,
            "crf": crf,
            "preset": preset,
            "pix_fmt": pix_fmt,
            "input_audio_path": input_audio_path,
        })
        size = self.sizes.pop(0) if len(self.sizes) > 1 else self.sizes[0]
        Path(out_path).write_bytes(b"\0" * size)


def _args(tmp_path: Path, **overrides):
    settings = {
        "input": str(tmp_path / "clip_in.mp4"),
        "output": str(tmp_path / "clip_out.mp4"),
        "loop_mode": "base-tip-base",
        "bridge_ms": 80.0,
        "bridge_frames": 1,
        "mode": "blend",
        "keep_length": True,
        "symmetric_blend": 0,
        "seam_ms": 0.0,
        "copy_audio": False,
        "crf": 12,
        "preset": "slow",
        "pix_fmt": "yuv420p",
        "max_mb": 1.0,
    }
    settings.update(overrides)
    return SimpleNamespace(**settings)


@pytest.fixture()
def run_pipeline(frames_of):
    """Drive postprocess_clip with the decode/probe/encode boundary stubbed."""
    def run(args, *, values=(10, 20, 30, 40), size=8, fps=24.0, encoder=None):
        encoder = encoder or _RecordingEncoder()
        with patch("clipper.clip_postprocess_pipeline.ffprobe_video",
                   return_value={"fps": fps, "width": size, "height": size,
                                 "nb_frames": len(values), "duration": len(values) / fps}) as probe, \
             patch("clipper.clip_postprocess_pipeline.read_frames",
                   return_value=frames_of(list(values), size=size)) as decode, \
             patch("clipper.clip_postprocess_pipeline.encode_with_ffmpeg", encoder):
            summary = postprocess_clip(args)
        probe.assert_called_once_with(args.input)
        decode.assert_called_once_with(args.input)
        return summary, encoder
    return run


def test_postprocess_clip_reports_the_clip_it_actually_encoded(tmp_path, run_pipeline):
    args = _args(tmp_path)

    summary, encoder = run_pipeline(args)

    assert summary == {
        "fps": 24.0,
        "input_frames": 4,
        "loop_mode": "base-tip-base",
        "normalized_frames": 4,
        "bridge_frames": 1,
        "output_frames": 4,
        "encode_attempts": 1,
        "final_scale": 1.0,
        "final_size_bytes": 16,
        "target_max_mb": 1.0,
        "output_path": args.output,
    }
    assert len(encoder.calls) == 1
    assert encoder.calls[0]["frame_count"] == 4
    assert encoder.calls[0]["fps"] == 24.0
    assert Path(args.output).exists()


def test_postprocess_clip_normalizes_the_loop_before_bridging(tmp_path, run_pipeline):
    """base-tip mirrors the four frames back to seven before the bridge lands."""
    summary, encoder = run_pipeline(_args(tmp_path, loop_mode="base-tip"))

    assert summary["normalized_frames"] == 7
    assert summary["output_frames"] == 7
    assert encoder.calls[0]["frame_count"] == 7


def test_postprocess_clip_appends_the_bridge_when_the_length_is_not_kept(tmp_path, run_pipeline):
    summary, encoder = run_pipeline(
        _args(tmp_path, keep_length=False, bridge_frames=2),
        values=(10, 20, 30, 40, 50, 60),
    )

    assert summary["normalized_frames"] == 6
    assert summary["bridge_frames"] == 2
    assert summary["output_frames"] == 8
    assert encoder.calls[0]["frame_count"] == 8


def test_postprocess_clip_caps_the_bridge_at_a_third_of_the_normalized_clip(tmp_path, run_pipeline):
    summary, _encoder = run_pipeline(_args(tmp_path, bridge_frames=3))

    assert summary["bridge_frames"] == 1


def test_postprocess_clip_shrinks_and_re_encodes_until_the_output_fits(tmp_path, run_pipeline):
    over = 2 * 1024 * 1024
    encoder = _RecordingEncoder(over, 4096)

    summary, encoder = run_pipeline(_args(tmp_path), size=80, encoder=encoder)

    assert summary["encode_attempts"] == 2
    assert summary["final_scale"] == pytest.approx(0.9)
    assert summary["final_size_bytes"] == 4096
    assert encoder.calls[0]["shape"] == (80, 80)
    assert encoder.calls[1]["shape"] == (72, 72)


def test_postprocess_clip_stops_shrinking_at_the_smallest_allowed_frame(tmp_path, run_pipeline, capsys):
    """It must give up rather than loop forever on a clip that will not fit."""
    encoder = _RecordingEncoder(2 * 1024 * 1024)

    summary, encoder = run_pipeline(_args(tmp_path), size=64, encoder=encoder)

    assert summary["encode_attempts"] == 1
    assert summary["final_scale"] == 1.0
    assert summary["final_size_bytes"] > 1024 * 1024
    assert "minimum allowed resolution" in capsys.readouterr().out


@pytest.mark.parametrize("copy_audio, expected_audio", [(True, "input"), (False, None)])
def test_postprocess_clip_keeps_the_input_audio_only_when_asked(
    tmp_path, run_pipeline, copy_audio, expected_audio
):
    args = _args(tmp_path, copy_audio=copy_audio)

    _summary, encoder = run_pipeline(args)

    want = args.input if expected_audio == "input" else None
    assert encoder.calls[0]["input_audio_path"] == want


def test_postprocess_clip_passes_the_encoder_settings_through(tmp_path, run_pipeline):
    _summary, encoder = run_pipeline(_args(tmp_path, crf=30, preset="veryfast", pix_fmt="yuv444p"))

    assert encoder.calls[0]["crf"] == 30
    assert encoder.calls[0]["preset"] == "veryfast"
    assert encoder.calls[0]["pix_fmt"] == "yuv444p"


def test_postprocess_clip_refuses_a_size_budget_of_zero(tmp_path, run_pipeline):
    with pytest.raises(RuntimeError, match="--max-mb must be greater than 0"):
        run_pipeline(_args(tmp_path, max_mb=0.0))


def test_postprocess_clip_refuses_a_clip_too_short_to_bridge(tmp_path, run_pipeline):
    with pytest.raises(RuntimeError, match="Clip is too short"):
        run_pipeline(_args(tmp_path), values=(10, 20))


# --seam-ms's blend sibling. Every case above passes symmetric_blend=0, so the
# branch that actually blends -- and the cap that decides how wide it gets --
# had no test at all. Sixteen frames, because the cap is a quarter of the clip
# and an eight-frame source makes it equal to the width asked for below, which
# is exactly the coincidence that lets a broken cap pass.
_BLEND_SOURCE = list(range(10, 170, 10))


def _blend_run(frames_of, values_of, symmetric_blend):
    """The frames the bridge is built from, for one --symmetric-blend width."""
    out, normalized_n = build_output_frames(
        frames_of(_BLEND_SOURCE), loop_mode="base-tip-base", bridge_frames=1,
        mode="blend", keep_length=False, symmetric_blend=symmetric_blend,
    )
    return values_of(out[:normalized_n]), normalized_n


def _moved(before, after):
    return [i for i, (a, b) in enumerate(zip(before, after)) if a != b]


def test_a_symmetric_blend_pulls_the_two_ends_toward_each_other(frames_of, values_of):
    plain, _ = _blend_run(frames_of, values_of, 0)

    blended, _ = _blend_run(frames_of, values_of, 2)

    assert abs(blended[0] - blended[-1]) < abs(plain[0] - plain[-1])


def test_it_moves_the_number_of_frames_at_each_end_that_was_asked_for(frames_of, values_of):
    plain, n = _blend_run(frames_of, values_of, 0)

    blended, _ = _blend_run(frames_of, values_of, 2)

    assert _moved(plain, blended) == [0, 1, n - 2, n - 1]


def test_a_blend_wider_than_a_quarter_of_the_clip_is_capped_there(frames_of, values_of):
    plain, n = _blend_run(frames_of, values_of, 0)
    quarter = n // 4

    greedy, _ = _blend_run(frames_of, values_of, 999)

    assert _moved(plain, greedy) == list(range(quarter)) + list(range(n - quarter, n))
    assert quarter < 999


def test_the_register_fallback_blends_the_same_way(frames_of, values_of):
    """Both bridge paths reach the blend; flat frames send register down the fallback."""
    blended, n = _blend_run(frames_of, values_of, 2)

    out, registered_n = build_output_frames(
        frames_of(_BLEND_SOURCE), loop_mode="base-tip-base", bridge_frames=1,
        mode="register", keep_length=False, symmetric_blend=2,
    )

    assert (values_of(out[:registered_n]), registered_n) == (blended, n)
