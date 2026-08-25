from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from clipper.clip_postprocess_transforms import (
    _find_rife_exe,
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


# The lookup walks the filesystem, so it runs once here rather than four times
# during collection, inside four decorators.
_RIFE_EXE = _find_rife_exe()
_NO_RIFE = pytest.mark.skipif(_RIFE_EXE is None, reason="RIFE binary not available")

_VENDORED = ("tools", "rife-ncnn-vulkan-20221029-windows", "rife-ncnn-vulkan.exe")


def _vendored_exe(root: Path) -> Path:
    exe = root.joinpath(*_VENDORED)
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"")
    return exe


class TestFindRifeExe:
    """Whether this returns a path gates four tests and the whole seam path.

    Its only unconditional test used to be `result is None or isinstance(result,
    str)`, which the return annotation already guarantees -- so a helper that
    returned a wrong-but-stringy path was indistinguishable from a working one.
    """

    def test_prefers_the_copy_vendored_into_the_checkout(self, tmp_path: Path):
        exe = _vendored_exe(tmp_path)

        with patch("clipper.clip_postprocess_transforms.shutil.which", return_value=None):
            assert _find_rife_exe(str(tmp_path)) == str(exe)

    def test_takes_the_vendored_copy_over_one_on_the_path(self, tmp_path: Path):
        exe = _vendored_exe(tmp_path)
        elsewhere = tmp_path / "on_path" / "rife-ncnn-vulkan"
        elsewhere.parent.mkdir()
        elsewhere.write_bytes(b"")

        with patch("clipper.clip_postprocess_transforms.shutil.which", return_value=str(elsewhere)):
            assert _find_rife_exe(str(tmp_path)) == str(exe)

    def test_falls_back_to_the_one_on_the_path(self, tmp_path: Path):
        elsewhere = tmp_path / "on_path" / "rife-ncnn-vulkan"
        elsewhere.parent.mkdir()
        elsewhere.write_bytes(b"")

        with patch("clipper.clip_postprocess_transforms.shutil.which", return_value=str(elsewhere)):
            assert _find_rife_exe(str(tmp_path)) == str(elsewhere)

    def test_is_none_when_the_checkout_has_no_vendored_copy(self, tmp_path: Path):
        with patch("clipper.clip_postprocess_transforms.shutil.which", return_value=None):
            assert _find_rife_exe(str(tmp_path)) is None

    def test_a_directory_where_the_executable_should_be_is_not_an_executable(self, tmp_path: Path):
        tmp_path.joinpath(*_VENDORED).mkdir(parents=True)

        with patch("clipper.clip_postprocess_transforms.shutil.which", return_value=None):
            assert _find_rife_exe(str(tmp_path)) is None


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
        M, inlier_ratio = estimate_alignment(frame, shifted)
        assert M is not None
        assert inlier_ratio > 0.3
        tx, ty, angle, scale = decompose_similarity(M, (64.0, 64.0))
        assert abs(tx - 5.0) < 2.0
        assert abs(ty - 3.0) < 2.0
        assert abs(angle) < 0.1
        assert abs(scale - 1.0) < 0.1

    def test_fails_on_blank_frames(self):
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        M, inlier_ratio = estimate_alignment(blank, blank)
        assert (M, inlier_ratio) == (None, 0.0)

    def test_fails_on_uniform_color(self):
        frame = np.full((64, 64, 3), 128, dtype=np.uint8)
        M, inlier_ratio = estimate_alignment(frame, frame)
        assert (M, inlier_ratio) == (None, 0.0)


class TestBuildRegisteredSeam:
    def test_reduces_endpoint_drift(self):
        frame = _make_textured_frame(128, 128, seed=10)
        # A ten-frame drift: the first frame, and the same frame shifted (8, 6).
        frames = []
        for i in range(10):
            t = i / 9.0
            M_t = np.array([[1, 0, 8 * t], [0, 1, 6 * t]], dtype=np.float32)
            frames.append(cv2.warpAffine(frame, M_t, (128, 128), borderMode=cv2.BORDER_REFLECT))

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
    def test_returns_none_with_zero_frames(self):
        frame = _make_textured_frame(64, 64)
        result = build_rife_bridge(frame, frame, 0)
        assert result is None

    @_NO_RIFE
    def test_produces_correct_count(self):
        frame_a = _make_textured_frame(128, 128, seed=1)
        frame_b = _make_textured_frame(128, 128, seed=2)
        result = build_rife_bridge(frame_a, frame_b, 3)
        assert result is not None
        assert len(result) == 3
        for f in result:
            assert f.shape == frame_a.shape
            assert f.dtype == np.uint8

    @_NO_RIFE
    def test_bridge_frames_differ_from_endpoints(self):
        frame_a = _make_textured_frame(128, 128, seed=10)
        frame_b = _make_textured_frame(128, 128, seed=20)
        result = build_rife_bridge(frame_a, frame_b, 1)
        assert result is not None
        mid = result[0]
        # The interpolated frame should not be identical to either endpoint
        assert not np.array_equal(mid, frame_a)
        assert not np.array_equal(mid, frame_b)


class TestRifeSeam:
    def test_returns_none_with_zero_seam_frames(self):
        frames = [_make_textured_frame(64, 64, seed=i) for i in range(10)]
        assert build_rife_seam(frames, 0) is None

    def test_returns_none_with_too_few_frames(self):
        frames = [_make_textured_frame(64, 64, seed=i) for i in range(3)]
        assert build_rife_seam(frames, 1) is None

    @_NO_RIFE
    def test_preserves_frame_count(self):
        frames = [_make_textured_frame(128, 128, seed=i) for i in range(10)]
        result = build_rife_seam(frames, 3)
        assert result is not None
        assert len(result) == len(frames)

    @_NO_RIFE
    def test_modifies_frames_near_seam(self):
        frames = [_make_textured_frame(128, 128, seed=i) for i in range(10)]
        result = build_rife_seam(frames, 3)
        assert result is not None
        # Frames nearest the seam should differ from originals
        assert not np.array_equal(result[0], frames[0])
        assert not np.array_equal(result[-1], frames[-1])
        # Middle frames should be unchanged (outside seam zone)
        assert np.array_equal(result[5], frames[5])
