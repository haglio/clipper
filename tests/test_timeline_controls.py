"""Tests for clipper.gui.timeline_controls — timeline manipulation buttons."""

from __future__ import annotations


import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.timeline_controls import TimelineControls


@pytest.fixture()
def ctl():
    return TimelineControls()


class TestSignals:
    def test_extend_left(self, ctl):
        results = []
        ctl.extend_left_clicked.connect(lambda: results.append(1))
        ctl.extend_left_btn.click()
        assert results == [1]

    def test_contract_left(self, ctl):
        results = []
        ctl.contract_left_clicked.connect(lambda: results.append(1))
        ctl.contract_left_btn.click()
        assert results == [1]

    def test_extend_right(self, ctl):
        results = []
        ctl.extend_right_clicked.connect(lambda: results.append(1))
        ctl.extend_right_btn.click()
        assert results == [1]

    def test_contract_right(self, ctl):
        results = []
        ctl.contract_right_clicked.connect(lambda: results.append(1))
        ctl.contract_right_btn.click()
        assert results == [1]

    def test_shift_left(self, ctl):
        results = []
        ctl.shift_left_clicked.connect(lambda: results.append(1))
        ctl.shift_left_btn.click()
        assert results == [1]

    def test_shift_right(self, ctl):
        results = []
        ctl.shift_right_clicked.connect(lambda: results.append(1))
        ctl.shift_right_btn.click()
        assert results == [1]

    def test_mark_in(self, ctl):
        results = []
        ctl.mark_in_clicked.connect(lambda: results.append(1))
        ctl.mark_in_btn.click()
        assert results == [1]

    def test_mark_out(self, ctl):
        results = []
        ctl.mark_out_clicked.connect(lambda: results.append(1))
        ctl.mark_out_btn.click()
        assert results == [1]

    def test_wrap_toggle(self, ctl):
        results = []
        ctl.wrap_clicked.connect(lambda: results.append(1))
        ctl.wrap_btn.click()
        assert results == [1]

    def test_loop_mode(self, ctl):
        results = []
        ctl.loop_mode_clicked.connect(lambda: results.append(1))
        ctl.loop_mode_btn.click()
        assert results == [1]


class TestLoopModeLabel:
    def test_set_loop_mode_uses_label(self, ctl):
        ctl.set_loop_mode("base-tip-base")
        assert ctl.loop_mode_btn.text() == "base-tip-base"

    def test_set_loop_mode_unknown_falls_back_to_raw(self, ctl):
        ctl.set_loop_mode("unknown-mode")
        assert ctl.loop_mode_btn.text() == "unknown-mode"
