"""Tests for clipper.gui.legend_widget — the painted hotkey legend."""

from __future__ import annotations

import pytest
from shared_ui.colors import BG_KEYCAP, BG_PRIMARY

from clipper.gui.legend_widget import LegendWidget
from clipper.gui.shortcuts import legend_rows


@pytest.fixture
def legend():
    widget = LegendWidget(legend_rows())
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

    def test_no_row_carries_more_than_two_fifths_of_the_legend(self, legend):
        """The rows are balanced so the widest fits the window's 900 px minimum.

        Measured with the family's font on Windows (Segoe UI) the three rows
        are 598, 736 and 638 px against the 884 px a row has there; before
        the repartition the six-entry bounds row was 959 px and its last entry
        drew off the right edge (bug 56).  The suite paints with the offscreen
        platform's stand-in font, which widens every row alike, so the
        invariant is a share of the whole rather than a pixel count: no row is
        more than two fifths of the three together.  An entry added to the
        wrong row reds this before it reaches the edge.
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

        assert max(widths) <= 0.4 * sum(widths), widths

    def test_a_wider_row_gets_more_keycap_ink_than_a_narrower_one(self, legend, rendered):
        legend.legend_rows = ((((("x",), "", "one"),)),)
        one_key = _keycap_pixels(rendered(legend), 0, legend.height())

        legend.legend_rows = (((("x",), "", "one"), (("y",), "", "two")),)
        two_keys = _keycap_pixels(rendered(legend), 0, legend.height())

        assert two_keys > one_key


def test_the_legend_does_not_need_the_video_decoder_to_be_imported():
    """It paints keycaps; it should not drag cv2 in behind them.

    The shortcut table names the editing functions, which reach `frame_store`,
    which imports cv2 -- so fetching the rows here rather than being handed
    them would make the decoder a requirement for importing a painter.  Run in
    a fresh interpreter with cv2 blocked, the way the other import checks in
    this suite are.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    probe = "import sys; sys.modules['cv2'] = None; import clipper.gui.legend_widget"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    result = subprocess.run([sys.executable, "-c", probe],
                            cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
