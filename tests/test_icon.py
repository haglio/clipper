"""Clipper's icon follows the family's icon spec."""

from __future__ import annotations

from shared_ui.app_icon import assert_follows_the_family_spec

from clipper.window_icons import clipper_icon_path


def test_the_icon_is_the_familys_c():
    # One MAGENTA block letter on the family's 5x5 grid, checked the way every
    # app's is.
    assert_follows_the_family_spec(clipper_icon_path(), "C")
