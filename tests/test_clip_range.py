"""Tests for clipper.clip_range — the in and out points of the clip."""
from __future__ import annotations

from clipper.clip_range import ClipRange


class TestMarkIn:
    def test_it_moves_the_in_point(self):
        clip = ClipRange(start=5, end=50)

        assert clip.mark_in(20) is True
        assert clip.start == 20

    def test_it_refuses_a_point_at_or_past_the_out_point(self):
        clip = ClipRange(start=5, end=50)

        assert clip.mark_in(50) is False
        assert clip.mark_in(55) is False
        assert clip.start == 5

    def test_the_anchor_follows_the_mark(self):
        """What the suggestion search searches around is where the mark was set."""
        clip = ClipRange(start=5, end=50, anchor_in=5)

        clip.mark_in(20)

        assert clip.anchor_in == 20

    def test_a_refused_mark_leaves_the_anchor_alone(self):
        clip = ClipRange(start=5, end=50, anchor_in=5)

        clip.mark_in(50)

        assert clip.anchor_in == 5


class TestMarkOut:
    def test_it_moves_the_out_point(self):
        clip = ClipRange(start=5, end=50)

        assert clip.mark_out(30) is True
        assert clip.end == 30

    def test_it_refuses_a_point_at_or_before_the_in_point(self):
        clip = ClipRange(start=20, end=50)

        assert clip.mark_out(20) is False
        assert clip.mark_out(10) is False
        assert clip.end == 50

    def test_the_anchor_follows_the_mark(self):
        clip = ClipRange(start=5, end=50, anchor_out=50)

        clip.mark_out(30)

        assert clip.anchor_out == 30


class TestShift:
    def test_it_carries_both_ends(self):
        clip = ClipRange(start=10, end=20)

        clip.shift(10)

        assert (clip.start, clip.end) == (20, 30)

    def test_it_re_anchors_on_the_new_ends(self):
        clip = ClipRange(start=10, end=20, anchor_in=10, anchor_out=20)

        clip.shift(-5)

        assert (clip.anchor_in, clip.anchor_out) == (5, 15)


class TestSpan:
    def test_the_span_is_how_far_a_shift_travels(self):
        assert ClipRange(start=10, end=20).span == 10
