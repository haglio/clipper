"""Tests for clipper.gui.playback_timer — QTimer-driven playback loop."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.playback_timer import PlaybackTimer


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def timer():
    return PlaybackTimer()


class TestConstruction:
    def test_interval(self, timer):
        assert timer.interval_ms == 16

    def test_not_running_initially(self, timer):
        assert not timer.is_running()


class TestStartStop:
    def test_start(self, timer):
        timer.start()
        assert timer.is_running()
        timer.stop()

    def test_stop(self, timer):
        timer.start()
        timer.stop()
        assert not timer.is_running()


class TestSignal:
    def test_tick_signal_exists(self, timer):
        # Verify the signal can be connected
        results = []
        timer.tick.connect(lambda: results.append(1))
        # Don't wait for real ticks — just verify wiring
        timer.tick.disconnect()
