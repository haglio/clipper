"""Tests for clipper.frame_cache_export."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from clipper.frame_cache_export import MAX_CACHE_MB, generate_frame_cache


def _make_test_video(
    path: Path, *, frames: int = 20, width: int = 200, height: int = 200, fps: float = 30.0
) -> None:
    """Create a small video with random-noise frames (hard to compress)."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    rng = np.random.RandomState(42)
    for _ in range(frames):
        writer.write(rng.randint(0, 256, (height, width, 3), dtype=np.uint8))
    writer.release()


class TestGenerateFrameCacheSizeCap:
    def test_quality_reduction_shrinks_cache(self, tmp_path: Path):
        """Tight max_mb forces quality reduction, producing a smaller cache."""
        video = tmp_path / "test.mp4"
        _make_test_video(video, frames=30, width=300, height=300)
        uncapped = tmp_path / "uncapped.rhcache"
        capped = tmp_path / "capped.rhcache"
        generate_frame_cache(video, uncapped)
        half_mb = (uncapped.stat().st_size / 2) / (1024 * 1024)
        generate_frame_cache(video, capped, max_mb=half_mb)
        assert capped.stat().st_size < uncapped.stat().st_size

    def test_achievable_cap_is_respected(self, tmp_path: Path):
        """When the cap is achievable, the output file stays under it."""
        video = tmp_path / "test.mp4"
        cache = tmp_path / "test.rhcache"
        _make_test_video(video, frames=5, width=100, height=100)
        max_mb = 1.0
        generate_frame_cache(video, cache, max_mb=max_mb)
        assert cache.stat().st_size <= max_mb * 1024 * 1024

    def test_default_cap_is_50mb(self):
        assert MAX_CACHE_MB == 50.0

    def test_no_max_mb_uses_default_cap(self, tmp_path: Path):
        """Callers that omit max_mb still get the 50 MB default."""
        video = tmp_path / "test.mp4"
        cache = tmp_path / "test.rhcache"
        _make_test_video(video, frames=5, width=100, height=100)
        generate_frame_cache(video, cache)  # no max_mb kwarg
        assert cache.exists()
        assert cache.stat().st_size <= MAX_CACHE_MB * 1024 * 1024
