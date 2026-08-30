"""Tests for clipper.wrap_modes — what the cursor wraps within."""
from __future__ import annotations

from clipper.wrap_modes import WRAP_OVER_ACTIVE, WRAP_OVER_LOADED, wrap_bounds


class TestWrapBounds:
    def test_over_the_loaded_range_the_cursor_roams_everything_loaded(self, make_state):
        state = make_state(loaded_start=10, loaded_end=60, active_start=20,
                           active_end=40, wrap_mode=WRAP_OVER_LOADED)

        assert wrap_bounds(state) == (10, 60)

    def test_over_the_active_range_it_is_held_to_the_clip(self, make_state):
        state = make_state(loaded_start=10, loaded_end=60, active_start=20,
                           active_end=40, wrap_mode=WRAP_OVER_ACTIVE)

        assert wrap_bounds(state) == (20, 40)

    def test_the_two_modes_are_the_colors_the_session_file_carries(self):
        """The session format is unversioned and evolver reads it, so the value
        stays the color it has always been; only the name says what it means."""
        assert (WRAP_OVER_LOADED, WRAP_OVER_ACTIVE) == ("blue", "yellow")


def test_nothing_else_spells_the_wrap_mode_out_as_a_color():
    """The two constants are the only place `"blue"` and `"yellow"` are written.

    They were the last thing this module was extracted to collect: the loader's
    default and the dataclass's still spelled the color while the creator next
    to them used the constant, so `grep WRAP_OVER_LOADED` did not find every
    place the default wrap mode is decided.
    """
    from pathlib import Path

    package = Path(__file__).resolve().parents[1] / "clipper"
    offenders = [
        f"{path.relative_to(package.parent).as_posix()}:{n}"
        for path in sorted(package.rglob("*.py"))
        if path.name != "wrap_modes.py"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if '"blue"' in line or '"yellow"' in line
    ]

    assert offenders == []
