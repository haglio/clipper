"""Tests for clipper.utils."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from clipper.utils import (
    FORBIDDEN_NAME_CHARS,
    format_seconds,
    parse_timestamp,
    safe_atomic_write_json,
    sanitize_name,
)


# ---------------------------------------------------------------------------
# parse_timestamp
# ---------------------------------------------------------------------------

# A clock string and the seconds it means. `parse_timestamp` reads what a user
# types; `_parse_ffmpeg_clock` reads what ffmpeg prints. Same shape, two
# parsers, so the cases live together and each runs against both.
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


# ---------------------------------------------------------------------------
# format_seconds
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# sanitize_name
# ---------------------------------------------------------------------------

class TestSanitizeName:
    def test_clean_name_unchanged(self):
        assert sanitize_name("clean name") == "clean name"

    def test_strips_leading_trailing_spaces(self):
        assert sanitize_name("  hello  ") == "hello"

    @pytest.mark.parametrize("forbidden", list(FORBIDDEN_NAME_CHARS))
    def test_every_character_a_filename_cannot_hold_becomes_an_underscore(self, forbidden):
        """Walks the module's own list, so adding a character adds a case."""
        assert sanitize_name(f"take{forbidden}one") == "take_one"

    def test_the_list_is_the_nine_windows_refuses(self):
        """One literal, so removing a character from the list is red too."""
        assert sanitize_name('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"

    def test_strips_trailing_dots(self):
        result = sanitize_name("filename.")
        assert not result.endswith(".")

    def test_a_name_of_only_spaces_becomes_the_empty_string(self):
        assert sanitize_name("   ") == ""


# ---------------------------------------------------------------------------
# safe_atomic_write_json
# ---------------------------------------------------------------------------

class TestSafeAtomicWriteJson:
    def test_writes_file(self, tmp_path: Path):
        target = tmp_path / "out.json"
        ok, err = safe_atomic_write_json(target, {"key": "value"})
        assert (ok, err) == (True, "")
        assert target.exists()

    def test_content_is_valid_json(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"answer": 42})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["answer"] == 42

    def test_no_tmp_file_left_after_success(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"x": 1})
        tmp = target.with_suffix(target.suffix + ".tmp")
        assert not tmp.exists()

    def test_returns_empty_error_on_success(self, tmp_path: Path):
        target = tmp_path / "out.json"
        ok, err = safe_atomic_write_json(target, {})
        assert ok is True
        assert err == ""

    def test_overwrites_existing_file(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"v": 1})
        safe_atomic_write_json(target, {"v": 2})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["v"] == 2

    def test_returns_false_on_permission_error(self, tmp_path: Path):
        target = tmp_path / "out.json"
        with patch("builtins.open", side_effect=PermissionError("denied")):
            ok, err = safe_atomic_write_json(target, {})
        assert ok is False
        assert "denied" in err

    def test_refuses_a_path_whose_parent_does_not_exist(self, tmp_path: Path):
        """It does not mkdir -- that is the caller's job -- but it must say so.

        The autosave warning the user sees is built from nothing but this
        return value, so a failure reported as a success is a session that
        silently stops being written.
        """
        target = tmp_path / "nested" / "dir" / "out.json"

        ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        # The path is named separator-agnostically: on Windows CPython formats
        # the OSError filename with repr() (doubling backslashes) and it names
        # the .tmp path, so the full str(target) is not a substring there.
        assert target.name in err
        assert not target.exists()

    def test_reports_a_failed_rename_and_leaves_no_half_written_file(self, tmp_path: Path):
        target = tmp_path / "out.json"

        with patch("clipper.utils.os.replace", side_effect=OSError("disk full")):
            ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        assert "disk full" in err
        assert not target.exists()
        assert not target.with_suffix(".json.tmp").exists()

    def test_a_tmp_file_it_cannot_clean_up_does_not_mask_the_failure(self, tmp_path: Path):
        target = tmp_path / "out.json"

        with patch("clipper.utils.os.replace", side_effect=OSError("disk full")), \
             patch("pathlib.Path.unlink", side_effect=OSError("still locked")):
            ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        assert "disk full" in err
