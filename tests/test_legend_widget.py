"""Tests for clipper.gui.legend_widget — the painted hotkey legend."""

from __future__ import annotations

import pytest

from shared_ui.colors import BG_KEYCAP, BG_PRIMARY

from clipper.gui.legend_widget import LegendWidget
from clipper.gui.shortcuts import legend_rows


@pytest.fixture()
def legend():
    widget = LegendWidget()
    widget.resize(900, 120)
    return widget


def _keycap_pixels(image, top: int, bottom: int) -> int:
    return sum(
        1
        for x in range(image.width())
        for y in range(top, bottom)
        if image.pixelColor(x, y).name() == BG_KEYCAP.name()
    )


class TestPainting:
    """The legend is drawn and nothing else; gutting paintEvent used to be
    caught only by the dead-code guard noticing the unused locals."""

    def test_every_row_of_the_legend_gets_keycaps(self, legend, rendered):
        image = rendered(legend)
        row_height = legend.height() // len(legend_rows())

        drawn = [
            _keycap_pixels(image, row * row_height, (row + 1) * row_height)
            for row in range(len(legend_rows()))
        ]

        assert all(count > 0 for count in drawn), drawn

    def test_a_legend_with_no_rows_is_bare_background(self, legend, rendered):
        legend.legend_rows = ()

        image = rendered(legend)

        assert _keycap_pixels(image, 0, image.height()) == 0
        assert image.pixelColor(450, 60).name() == BG_PRIMARY.name()

    def test_only_the_bounds_row_is_too_wide_for_the_smallest_window(self, legend):
        """The legend is generated now, so an added entry could push a row off
        the edge.  At the window's 900x600 minimum exactly one row already
        does: the six-entry bounds row, at 994px against 900.  That overflow
        predates the generated legend (it measures the same before and after)
        and is recorded rather than fixed -- how to make it fit is a layout
        decision.  This is the ratchet: a second one reds.
        """
        from PyQt6.QtGui import QFont, QImage, QPainter

        from shared_ui.fonts import FONT_UI, SIZE_SMALL, SIZE_TINY

        legend.resize(900, 80)
        image = QImage(900, 80, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        keycap = QFont(FONT_UI, SIZE_SMALL)
        keycap.setBold(True)
        small = QFont(FONT_UI, SIZE_TINY)
        widths = [
            legend._row_width(painter, row, keycap, small, small)
            for row in legend.legend_rows
        ]
        painter.end()

        too_wide = [i for i, width in enumerate(widths) if width > 900 - 16]
        assert too_wide == [1], widths

    def test_a_wider_row_gets_more_keycap_ink_than_a_narrower_one(self, legend, rendered):
        legend.legend_rows = ((((("x",), "", "one"),)),)
        one_key = _keycap_pixels(rendered(legend), 0, legend.height())

        legend.legend_rows = (((("x",), "", "one"), (("y",), "", "two")),)
        two_keys = _keycap_pixels(rendered(legend), 0, legend.height())

        assert two_keys > one_key
