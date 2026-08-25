"""Tests for clipper.gui.playback_timer — QTimer-driven playback loop."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
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
    def test_the_tick_fires_once_the_timer_is_started(self, timer):
        """The whole animation loop hangs off this signal.

        The old test connected a slot, disconnected it and asserted nothing, so
        a timer that never fired -- or one whose interval had grown to five
        seconds -- passed.
        """
        ticks = []
        timer.tick.connect(lambda: ticks.append(1))

        loop = QEventLoop()
        timer.tick.connect(loop.quit)
        QTimer.singleShot(2000, loop.quit)  # a bound, not a wait
        timer.start()
        loop.exec()
        timer.stop()

        assert ticks

    def test_it_ticks_fast_enough_for_smooth_playback(self, timer):
        assert 0 < timer.interval_ms <= 20
