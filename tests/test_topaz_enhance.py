"""Tests for clipper.topaz_enhance (pure-logic helpers only)."""
from __future__ import annotations

import pytest

from clipper.topaz_enhance import _compute_upscale_factor


class TestComputeUpscaleFactor:
    def test_respects_max_mb_cache_estimate(self):
        """Scale is reduced when estimated cache exceeds max_mb."""
        # 1920x1080 @ 4x = 7680x4320, 240 frames
        # estimated_cache_mb = 7680*4320*0.5*240 / 1M ≈ 3796 MB → way over 50 MB
        # At 1x: 1920*1080*0.5*240 / 1M ≈ 237 MB → still over 50
        # Use a smaller input where 2x fits but 4x doesn't
        w, h = 200, 200
        target_frames = 240
        duration = 4.0
        # At 4x: 800*800*0.5*240/1M ≈ 73 MB → over 50
        # At 3x: 600*600*0.5*240/1M ≈ 41 MB → under 50
        scale = _compute_upscale_factor(w, h, target_frames, duration, max_mb=50.0)
        assert scale <= 3

    def test_generous_max_mb_allows_higher_scale(self):
        """With no effective size constraint, scale goes higher."""
        w, h = 200, 200
        target_frames = 240
        duration = 4.0
        scale = _compute_upscale_factor(w, h, target_frames, duration, max_mb=500.0)
        assert scale == 4
