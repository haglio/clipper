from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from clipper import clip_postprocess_transforms, interpolator_environment
from clipper.clip_postprocess_transforms import (
    build_registered_seam,
    build_rife_bridge,
    build_rife_seam,
    compose_similarity,
    decompose_similarity,
    estimate_alignment,
    fractional_similarity,
)


def _make_textured_frame(w: int = 128, h: int = 128, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randint(0, 256, (h, w, 3), dtype=np.uint8)


@pytest.fixture
def interpolator(tmp_path: Path, monkeypatch) -> None:
    """A checkout that has fetched the interpolator, and a stand-in for the
    binary: it reads the two frames the app wrote and writes a blend of them
    where the app will look for one.

    Everything either side of the process boundary therefore runs for real --
    the PNGs written and read back, the timesteps, which frames get replaced --
    and only the neural network is invented.  These four ran nowhere but a
    machine that had fetched 17 MB of Windows binary and owned a Vulkan device,
    which is neither the merge gate nor most of the machines here.  A flag the
    real binary would reject still reds them, since the stand-in reads the same
    five by name; that it turns them into a frame is asserted by the gate's own
    ``python tools/fetch_rife.py --require``.
    """
    exe = tmp_path / interpolator_environment.VENDORED_EXE
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    model_dir = exe.parent / interpolator_environment.MODEL_DIR_NAME
    model_dir.mkdir()
    for name in interpolator_environment.MODEL_FILES:
        (model_dir / name).write_bytes(b"weights")
    monkeypatch.setattr(interpolator_environment, "PROJECT_DIR", tmp_path)

    def _blend(cmd, **_kwargs):
        args = [str(part) for part in cmd]
        flags = dict(zip(args[1::2], args[2::2]))
        timestep = float(flags["-s"])
        cv2.imwrite(flags["-o"], cv2.addWeighted(
            cv2.imread(flags["-0"], cv2.IMREAD_COLOR), 1.0 - timestep,
            cv2.imread(flags["-1"], cv2.IMREAD_COLOR), timestep, 0.0))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(clip_postprocess_transforms.subprocess, "run", _blend)


class TestDecomposeComposeSimilarity:
    def test_roundtrip_identity(self):
        center = (64.0, 64.0)
        M = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float64)
        tx, ty, angle, scale = decompose_similarity(M, center)
        assert abs(tx) < 1e-9
        assert abs(ty) < 1e-9
        assert abs(angle) < 1e-9
        assert abs(scale - 1.0) < 1e-9

    def test_roundtrip_translation(self):
        center = (64.0, 64.0)
        M = compose_similarity(5.5, -3.2, 0.0, 1.0, center)
        tx, ty, angle, scale = decompose_similarity(M, center)
        assert abs(tx - 5.5) < 1e-6
        assert abs(ty - (-3.2)) < 1e-6
        assert abs(angle) < 1e-9        # a translation turns nothing
        assert abs(scale - 1.0) < 1e-9  # and resizes nothing

    def test_roundtrip_known_transform(self):
        center = (64.0, 64.0)
        tx, ty, angle, scale = 3.0, -2.0, 0.1, 1.05
        M = compose_similarity(tx, ty, angle, scale, center)
        tx2, ty2, angle2, scale2 = decompose_similarity(M, center)
        assert abs(tx2 - tx) < 1e-6
        assert abs(ty2 - ty) < 1e-6
        assert abs(scale2 - scale) < 1e-6
        assert abs(angle2 - angle) < 1e-6


class TestFractionalSimilarity:
    def test_zero_gives_identity(self):
        center = (64.0, 64.0)
        M = compose_similarity(10.0, -5.0, 0.2, 1.1, center)
        M_frac = fractional_similarity(M, 0.0, center)
        # Should be identity
        assert abs(M_frac[0, 0] - 1.0) < 1e-6
        assert abs(M_frac[1, 1] - 1.0) < 1e-6
        assert abs(M_frac[0, 1]) < 1e-6
        assert abs(M_frac[1, 0]) < 1e-6
        assert abs(M_frac[0, 2]) < 1e-6
        assert abs(M_frac[1, 2]) < 1e-6

    def test_one_gives_original(self):
        center = (64.0, 64.0)
        M = compose_similarity(10.0, -5.0, 0.2, 1.1, center)
        M_frac = fractional_similarity(M, 1.0, center)
        np.testing.assert_allclose(M_frac, M, atol=1e-6)

    def test_half_is_between(self):
        center = (64.0, 64.0)
        M = compose_similarity(10.0, 0.0, 0.0, 1.0, center)
        M_half = fractional_similarity(M, 0.5, center)
        # For pure translation, halfway should give half the translation
        assert abs(M_half[0, 2] - 5.0) < 1e-6


class TestEstimateAlignment:
    def test_recovers_known_shift(self):
        frame = _make_textured_frame(128, 128, seed=7)
        # Shift by 5 pixels right and 3 pixels down
        M_shift = np.array([[1, 0, 5], [0, 1, 3]], dtype=np.float32)
        shifted = cv2.warpAffine(frame, M_shift, (128, 128), borderMode=cv2.BORDER_REFLECT)
        M = estimate_alignment(frame, shifted)
        assert M is not None
        tx, ty, angle, scale = decompose_similarity(M, (64.0, 64.0))
        assert abs(tx - 5.0) < 2.0
        assert abs(ty - 3.0) < 2.0
        assert abs(angle) < 0.1
        assert abs(scale - 1.0) < 0.1

    def test_fails_on_blank_frames(self):
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        assert estimate_alignment(blank, blank) is None

    def test_fails_on_uniform_color(self):
        frame = np.full((64, 64, 3), 128, dtype=np.uint8)
        assert estimate_alignment(frame, frame) is None


class TestBuildRegisteredSeam:
    def test_reduces_endpoint_drift(self, textured_frames):
        frames = textured_frames()

        diff_before = np.mean(np.abs(frames[-1].astype(float) - frames[0].astype(float)))
        result, ok = build_registered_seam(frames, seam_frames=3)
        assert ok is True
        diff_after = np.mean(np.abs(result[-1].astype(float) - result[0].astype(float)))
        assert diff_after < diff_before

    def test_fallback_on_uniform_frames(self):
        frames = [np.full((64, 64, 3), 128, dtype=np.uint8) for _ in range(6)]
        result, ok = build_registered_seam(frames, seam_frames=2)
        assert ok is False
        # Frames should be returned unchanged
        for orig, out in zip(frames, result):
            np.testing.assert_array_equal(orig, out)

    def test_too_few_frames(self):
        frame = _make_textured_frame(64, 64)

        result, ok = build_registered_seam([frame], seam_frames=1)

        assert ok is False
        np.testing.assert_array_equal(result[0], frame)


class TestRifeBridge:
    def test_an_empty_clip_offers_no_seam(self):
        frame = _make_textured_frame(64, 64)
        result = build_rife_bridge(frame, frame, 0)
        assert result is None

    def test_produces_correct_count(self, interpolator):
        frame_a = _make_textured_frame(128, 128, seed=1)
        frame_b = _make_textured_frame(128, 128, seed=2)
        result = build_rife_bridge(frame_a, frame_b, 3)
        assert result is not None
        assert len(result) == 3
        for f in result:
            assert f.shape == frame_a.shape
            assert f.dtype == np.uint8

    def test_bridge_frames_differ_from_endpoints(self, interpolator):
        frame_a = _make_textured_frame(128, 128, seed=10)
        frame_b = _make_textured_frame(128, 128, seed=20)
        result = build_rife_bridge(frame_a, frame_b, 1)
        assert result is not None
        mid = result[0]
        # The interpolated frame should not be identical to either endpoint
        assert not np.array_equal(mid, frame_a)
        assert not np.array_equal(mid, frame_b)


class TestRifeSeam:
    def test_a_clip_with_no_seam_frames_offers_no_seam(self):
        frames = [_make_textured_frame(64, 64, seed=i) for i in range(10)]
        assert build_rife_seam(frames, 0) is None

    def test_a_clip_too_short_to_align_offers_no_seam(self):
        frames = [_make_textured_frame(64, 64, seed=i) for i in range(3)]
        assert build_rife_seam(frames, 1) is None

    def test_preserves_frame_count(self, interpolator):
        frames = [_make_textured_frame(128, 128, seed=i) for i in range(10)]
        result = build_rife_seam(frames, 3)
        assert result is not None
        assert len(result) == len(frames)

    def test_modifies_frames_near_seam(self, interpolator):
        frames = [_make_textured_frame(128, 128, seed=i) for i in range(10)]
        result = build_rife_seam(frames, 3)
        assert result is not None
        # Frames nearest the seam should differ from originals
        assert not np.array_equal(result[0], frames[0])
        assert not np.array_equal(result[-1], frames[-1])
        # Middle frames should be unchanged (outside seam zone)
        assert np.array_equal(result[5], frames[5])
