"""Tests for clipper.gui.shortcuts — the one keymap.

It was written out four times in three modules and the copies had drifted; the
tests here are the guards that stop that happening again.
"""
from __future__ import annotations

import pytest

from clipper.gui.shortcuts import LEGEND_ROWS, SHORTCUTS, legend_rows, shortcut_for


class TestTheTableIsWellFormed:
    def test_no_two_shortcuts_claim_the_same_typed_key(self):
        claimed: dict[str, str] = {}
        for shortcut in SHORTCUTS:
            for key in shortcut.keys:
                assert key not in claimed, f"{key!r}: {claimed.get(key)} and {shortcut.name}"
                claimed[key] = shortcut.name

    def test_no_two_shortcuts_claim_the_same_key_code(self):
        claimed: dict[int, str] = {}
        for shortcut in SHORTCUTS:
            for code in shortcut.qt_keys:
                assert code not in claimed
                claimed[code] = shortcut.name

    def test_every_shortcut_can_be_reached_by_something(self):
        for shortcut in SHORTCUTS:
            assert shortcut.keys or shortcut.qt_keys, shortcut.name

    def test_every_printed_keycap_is_a_key_that_reaches_the_action(self):
        """The legend cannot advertise a key the handler does not accept."""
        for shortcut in SHORTCUTS:
            for keycap in shortcut.keycaps:
                assert keycap in shortcut.keys or keycap in _named_codes(shortcut), shortcut.name


def _named_codes(shortcut) -> set[str]:
    """Keycaps for the keys that carry no text: `left`, `space`, `enter`."""
    return {code.name.removeprefix("Key_").lower() for code in shortcut.qt_keys}


class TestTheLegendComesFromTheTable:
    def test_every_shortcut_appears_in_exactly_one_legend_entry(self):
        """The drift this closes: `q` was bound and the legend never said so."""
        listed = [name for row in LEGEND_ROWS for names, _, _ in row for name in names]

        assert sorted(listed) == sorted(s.name for s in SHORTCUTS)

    def test_a_legend_entry_prints_the_keycaps_of_the_shortcuts_it_names(self):
        rendered = legend_rows()
        speed = rendered[0][0]

        assert speed == (("-", "+"), " or ", "speed")

    def test_the_rendered_legend_has_the_shape_the_widget_paints(self):
        for row in legend_rows():
            for keys, joiner, label in row:
                assert isinstance(keys, tuple) and keys
                assert isinstance(joiner, str)
                assert isinstance(label, str) and label


class TestLookup:
    @pytest.mark.parametrize("text, name", [
        ("a", "extend_left"),
        ("[", "mark_in"),
        ("_", "speed_down"),
        ("=", "speed_up"),
        ("9", "accept_in"),
        ("q", "quit"),
    ])
    def test_a_typed_key_finds_its_shortcut(self, text, name):
        found = shortcut_for(0, text)

        assert found is not None and found.name == name

    def test_a_key_code_finds_its_shortcut(self):
        from PyQt6.QtCore import Qt

        found = shortcut_for(Qt.Key.Key_Left, "")

        assert found is not None and found.name == "cursor_left"

    def test_an_unbound_key_finds_nothing(self):
        assert shortcut_for(0, "z") is None
