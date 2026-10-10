"""Genaumacher's icon follows the family's icon spec."""

from __future__ import annotations

from shared_ui.app_icon import assert_follows_the_family_spec

from genaumacher.window_icons import genaumacher_icon_path


def test_the_icon_is_the_familys_g():
    # One MAGENTA block letter on the family's 5x5 grid, checked the way every
    # app's is.
    assert_follows_the_family_spec(genaumacher_icon_path(), "G")
