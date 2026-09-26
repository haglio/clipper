"""Tests for clipper.gui.button_bar — transport control buttons."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtGui import QIcon
from shared_ui.chrome import family_stylesheet
from shared_ui.colors import TEXT_PRIMARY
from shared_ui.icon_geometry import GLYPHS, Polygon
from shared_ui.icons import glyph_pixmap
from shared_ui.spacing import BUTTON_SIZE

from clipper.gui.button_bar import ButtonBar


@pytest.fixture
def bar():
    return ButtonBar()


class TestSignals:
    def test_speed_down_emits(self, bar):
        results = []
        bar.speed_down_clicked.connect(lambda: results.append("down"))
        bar.speed_down_btn.click()
        assert results == ["down"]

    def test_speed_up_emits(self, bar):
        results = []
        bar.speed_up_clicked.connect(lambda: results.append("up"))
        bar.speed_up_btn.click()
        assert results == ["up"]

    def test_play_pause_emits(self, bar):
        results = []
        bar.play_pause_clicked.connect(lambda: results.append("pp"))
        bar.play_pause_btn.click()
        assert results == ["pp"]

    def test_export_emits(self, bar):
        results = []
        bar.export_clicked.connect(lambda: results.append("export"))
        bar.export_btn.click()
        assert results == ["export"]


def test_the_transport_wears_the_familys_marks(bar):
    """Fun Time's bar and Evolver's Run Now draw these same marks, and all three
    apps sit open together.  These were an icon font's, at its weight."""

    size = QSize(48, 48)

    for icon, name in ((bar._icon_play, "play"),
                       (bar._icon_pause, "pause"),
                       (bar.speed_down_btn.icon(), "minus"),
                       (bar.speed_up_btn.icon(), "plus")):
        drawn = icon.pixmap(size, QIcon.Mode.Normal).toImage()
        assert drawn == glyph_pixmap(name, 48, TEXT_PRIMARY).toImage(), name


def test_the_play_triangle_has_rounded_corners():
    """Which is what the icon font gave it, and what the family's own drawing
    lacked until filled shapes took a corner radius."""

    triangle = next(s for s in GLYPHS["play"] if isinstance(s, Polygon))
    assert triangle.round_radius > 0


def _where_the_mark_lands(button) -> QRect:
    worn = button.grab().toImage()
    icon = button.icon()
    button.setIcon(QIcon())
    bare = button.grab().toImage()
    button.setIcon(icon)
    inked = [(x, y) for y in range(worn.height()) for x in range(worn.width())
             if worn.pixel(x, y) != bare.pixel(x, y)]
    xs, ys = [x for x, _ in inked], [y for _, y in inked]
    return QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))


def _transport(bar):
    return (bar.speed_down_btn, bar.speed_up_btn, bar.play_pause_btn)


def test_each_transport_button_is_the_familys_ordinary_square(bar):
    for button in _transport(bar):
        assert button.size() == QSize(BUTTON_SIZE, BUTTON_SIZE)


def test_each_transport_mark_spans_more_than_half_its_button(bar):
    bar.setStyleSheet(family_stylesheet())
    bar.show()

    for button in _transport(bar):
        mark = _where_the_mark_lands(button)
        assert max(mark.width(), mark.height()) > BUTTON_SIZE / 2
