"""Tests for clipper.gui.button_bar — transport control buttons."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.button_bar import ButtonBar


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
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


class TestPlayPauseLabel:
    def test_default_is_play(self, bar):
        assert "Play" in bar.play_pause_btn.text() or "play" in bar.play_pause_btn.text().lower()

    def test_set_playing(self, bar):
        bar.set_playing(True)
        assert "pause" in bar.play_pause_btn.text().lower()

    def test_set_paused(self, bar):
        bar.set_playing(True)
        bar.set_playing(False)
        assert "play" in bar.play_pause_btn.text().lower()
