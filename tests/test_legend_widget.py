"""Tests for clipper.gui.legend_widget — the painted hotkey legend."""

from __future__ import annotations

import pytest

from shared_ui.colors import BG_KEYCAP, BG_PRIMARY

from clipper.gui.legend_widget import HOTKEY_LEGEND_ROWS, LegendWidget


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
        row_height = legend.height() // len(HOTKEY_LEGEND_ROWS)

        drawn = [
            _keycap_pixels(image, row * row_height, (row + 1) * row_height)
            for row in range(len(HOTKEY_LEGEND_ROWS))
        ]

        assert all(count > 0 for count in drawn), drawn

    def test_a_legend_with_no_rows_is_bare_background(self, legend, rendered):
        legend.legend_rows = ()

        image = rendered(legend)

        assert _keycap_pixels(image, 0, image.height()) == 0
        assert image.pixelColor(450, 60).name() == BG_PRIMARY.name()

    def test_a_wider_row_gets_more_keycap_ink_than_a_narrower_one(self, legend, rendered):
        legend.legend_rows = ((((("x",), "", "one"),)),)
        one_key = _keycap_pixels(rendered(legend), 0, legend.height())

        legend.legend_rows = (((("x",), "", "one"), (("y",), "", "two")),)
        two_keys = _keycap_pixels(rendered(legend), 0, legend.height())

        assert two_keys > one_key
