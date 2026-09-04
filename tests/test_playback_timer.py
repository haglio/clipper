"""Tests for clipper.gui.playback_timer — QTimer-driven playback loop."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.playback_timer import PlaybackTimer


@pytest.fixture
def timer():
    return PlaybackTimer()


class TestTicking:
    """The whole animation loop hangs off this signal.

    Its old test connected a slot, disconnected it and asserted nothing, and
    start/stop were read off the private QTimer -- so a timer that never fired,
    or whose interval had grown to five seconds, passed either way.
    """

    def test_a_new_timer_does_not_tick(self, timer, ticked_within):
        assert ticked_within(timer.tick, 100) is False

    def test_it_ticks_once_started(self, timer, ticked_within):
        timer.start()
        try:
            assert ticked_within(timer.tick, 2000) is True
        finally:
            timer.stop()

    def test_it_stops_ticking_when_stopped(self, timer, ticked_within):
        timer.start()
        assert ticked_within(timer.tick, 2000) is True

        timer.stop()
        QApplication.processEvents()  # drain a tick already on its way

        assert ticked_within(timer.tick, 100) is False

    def test_it_ticks_fast_enough_for_smooth_playback(self, timer):
        assert 0 < timer.interval_ms <= 20
