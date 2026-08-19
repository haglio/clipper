"""Clipper's chrome takes its colors from the family's palette, not its own.

Most of it always did -- the timeline, the legend and the video pane all read
shared_ui tokens.  What was left were the strays: the button fill, its hover and
pressed shades, two borders and a brace stroke, each written as a hex literal
nobody else in the family used.  Strays like those are why one app ends up
looking a shade off from the one beside it, so this walks the GUI source and
fails on any color spelled out in place.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_GUI = Path(__file__).resolve().parent.parent / "clipper" / "gui"

# "#abc" and "#aabbcc" -- how a color reaches a Qt stylesheet when it did not
# come from a token.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


def _sources() -> list[Path]:
    files = sorted(_GUI.glob("*.py"))
    assert files, "no GUI modules found to check"
    return files


def test_no_color_is_spelled_out_in_a_stylesheet():
    # Parsed rather than grepped, so a "#" in a comment or a path is not a hit --
    # only text the app actually hands to Qt.
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for match in _HEX.findall(node.value):
                    offenders.append(f"{path.name}:{node.lineno} {match}")
    assert not offenders, (
        "colors written in place instead of taken from shared_ui.colors: "
        + ", ".join(offenders)
    )


def test_no_color_is_built_from_raw_channel_numbers():
    # QColor(200, 200, 200) is the same stray wearing a constructor.
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None))
            if name != "QColor" or not node.args:
                continue
            if all(isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float))
                   for arg in node.args):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "colors built from raw channels instead of taken from shared_ui.colors: "
        + ", ".join(offenders)
    )


def test_the_chrome_reads_the_family_palette():
    # The positive side of it: the GUI does import the tokens, so the two checks
    # above are not passing merely because nothing here draws anything.
    importers = [
        path.name for path in _sources()
        if "shared_ui.colors" in path.read_text(encoding="utf-8")
    ]
    assert "main_window.py" in importers
    assert "button_bar.py" in importers


def test_a_control_that_is_on_sits_on_a_lighter_ground():
    """One rule across the family, so a toggled button reads the same whichever
    app it is in.  Origenerator had it and this did not."""
    from clipper.gui.main_window import _BTN_STYLE
    from shared_ui.colors import BG_BUTTON, BG_BUTTON_ACTIVE

    assert BG_BUTTON_ACTIVE.name() in _BTN_STYLE
    assert ":checked" in _BTN_STYLE
    assert BG_BUTTON.name() in _BTN_STYLE   # and a resting one still sits darker
