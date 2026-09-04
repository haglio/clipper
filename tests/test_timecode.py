"""Tests for clipper.timecode -- seconds to and from a clock string."""
from __future__ import annotations

import pytest

from clipper.timecode import format_seconds, parse_timestamp

_CLOCKS = [
    ("00:00:00", 0.0),
    ("00:00:30", 30.0),
    ("00:01:30", 90.0),
    ("01:00:00", 3600.0),
    ("00:00:01.500", 1.5),
    ("01:02:03.250", 3723.25),
]


class TestParseTimestamp:
    @pytest.mark.parametrize("clock, seconds", _CLOCKS)
    def test_it_reads_a_clock_as_seconds(self, clock, seconds):
        assert parse_timestamp(clock) == pytest.approx(seconds)

    def test_it_ignores_the_whitespace_around_what_was_typed(self):
        assert parse_timestamp("  00:00:05  ") == pytest.approx(5.0)

    @pytest.mark.parametrize("typed", ["00:30", "00:00:00:00"])
    def test_anything_that_is_not_hours_minutes_seconds_is_refused(self, typed):
        with pytest.raises(ValueError, match="Timestamp must be"):
            parse_timestamp(typed)


class TestFormatSeconds:
    def test_zero(self):
        assert format_seconds(0.0) == "00:00:00.000"

    def test_negative_clamped_to_zero(self):
        assert format_seconds(-5.0) == "00:00:00.000"

    def test_whole_seconds(self):
        assert format_seconds(30.0) == "00:00:30.000"

    def test_minutes(self):
        assert format_seconds(90.0) == "00:01:30.000"

    def test_hours(self):
        assert format_seconds(3600.0) == "01:00:00.000"

    def test_fractional_seconds(self):
        result = format_seconds(1.5)
        assert result == "00:00:01.500"

    def test_roundtrip_with_parse(self):
        original = 3723.25
        assert parse_timestamp(format_seconds(original)) == pytest.approx(original, rel=1e-5)
