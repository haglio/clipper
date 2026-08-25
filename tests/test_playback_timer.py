"""Tests for clipper.gui.playback_timer — QTimer-driven playback loop."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEventLoop, QTimer

from clipper.gui.playback_timer import PlaybackTimer


@pytest.fixture()
def timer():
    return PlaybackTimer()


def _ticked_within(timer: PlaybackTimer, budget_ms: int) -> bool:
    """Whether a tick arrives inside the budget; returns as soon as one does."""
    seen = []
    loop = QEventLoop()

    def on_tick():
        seen.append(1)
        loop.quit()

    timer.tick.connect(on_tick)
    QTimer.singleShot(budget_ms, loop.quit)
    loop.exec()
    timer.tick.disconnect(on_tick)
    return bool(seen)


class TestTicking:
    """The whole animation loop hangs off this signal.

    Its old test connected a slot, disconnected it and asserted nothing, and
    start/stop were read off the private QTimer -- so a timer that never fired,
    or whose interval had grown to five seconds, passed either way.
    """

    def test_a_new_timer_does_not_tick(self, timer):
        assert _ticked_within(timer, 100) is False

    def test_it_ticks_once_started(self, timer):
        timer.start()
        try:
            assert _ticked_within(timer, 2000) is True
        finally:
            timer.stop()

    def test_it_stops_ticking_when_stopped(self, timer):
        timer.start()
        assert _ticked_within(timer, 2000) is True

        timer.stop()

        assert _ticked_within(timer, 100) is False

    def test_it_ticks_fast_enough_for_smooth_playback(self, timer):
        assert 0 < timer.interval_ms <= 20
