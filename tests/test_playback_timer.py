"""Tests for clipper.gui.playback_timer — QTimer-driven playback loop."""

from __future__ import annotations


import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.playback_timer import PlaybackTimer


@pytest.fixture()
def timer():
    return PlaybackTimer()


class TestStartStop:
    def test_start(self, timer):
        timer.start()
        assert timer._timer.isActive()
        timer.stop()

    def test_stop(self, timer):
        timer.start()
        timer.stop()
        assert not timer._timer.isActive()


class TestSignal:
    def test_tick_signal_exists(self, timer):
        # Verify the signal can be connected
        results = []
        timer.tick.connect(lambda: results.append(1))
        # Don't wait for real ticks — just verify wiring
        timer.tick.disconnect()
