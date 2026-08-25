"""Tests for clipper.gui.timeline_controls — timeline manipulation buttons."""

from __future__ import annotations


import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.timeline_controls import TimelineControls


@pytest.fixture()
def ctl():
    return TimelineControls()


# Every button on the row and the signal it must emit. Ten copies of the same
# three lines before; a button added without a row here is a button whose wiring
# nothing checks.
_BUTTONS = [
    ("extend_left", "extend_left_btn", "extend_left_clicked"),
    ("contract_left", "contract_left_btn", "contract_left_clicked"),
    ("extend_right", "extend_right_btn", "extend_right_clicked"),
    ("contract_right", "contract_right_btn", "contract_right_clicked"),
    ("shift_left", "shift_left_btn", "shift_left_clicked"),
    ("shift_right", "shift_right_btn", "shift_right_clicked"),
    ("mark_in", "mark_in_btn", "mark_in_clicked"),
    ("mark_out", "mark_out_btn", "mark_out_clicked"),
    ("wrap", "wrap_btn", "wrap_clicked"),
    ("loop_mode", "loop_mode_btn", "loop_mode_clicked"),
]


class TestSignals:
    @pytest.mark.parametrize(
        "button, signal",
        [pytest.param(b, sig, id=label) for label, b, sig in _BUTTONS],
    )
    def test_clicking_a_button_emits_its_signal(self, ctl, button, signal):
        fired = []
        getattr(ctl, signal).connect(lambda: fired.append(1))

        getattr(ctl, button).click()

        assert fired == [1]

    @pytest.mark.parametrize(
        "button, signal",
        [pytest.param(b, sig, id=label) for label, b, sig in _BUTTONS],
    )
    def test_no_other_button_emits_it(self, ctl, button, signal):
        """A signal wired to two buttons would pass the test above twice over."""
        fired = []
        getattr(ctl, signal).connect(lambda: fired.append(1))

        for _label, other, _sig in _BUTTONS:
            if other != button:
                getattr(ctl, other).click()

        assert fired == []


class TestLoopModeLabel:
    def test_set_loop_mode_uses_label(self, ctl):
        ctl.set_loop_mode("base-tip-base")
        assert ctl.loop_mode_btn.text() == "base-tip-base"

    def test_set_loop_mode_unknown_falls_back_to_raw(self, ctl):
        ctl.set_loop_mode("unknown-mode")
        assert ctl.loop_mode_btn.text() == "unknown-mode"
