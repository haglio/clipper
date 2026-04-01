"""Tests for clipper.gui.timeline_controls — timeline manipulation buttons."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.timeline_controls import TimelineControls


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


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


class TestWrapLabel:
    def test_set_wrap_mode_blue(self, ctl):
        ctl.set_wrap_mode("blue")
        assert "blue" in ctl.wrap_btn.text().lower() or "loaded" in ctl.wrap_btn.text().lower()

    def test_set_wrap_mode_yellow(self, ctl):
        ctl.set_wrap_mode("yellow")
        assert "yellow" in ctl.wrap_btn.text().lower() or "active" in ctl.wrap_btn.text().lower()


class TestLoopModeLabel:
    def test_set_loop_mode(self, ctl):
        ctl.set_loop_mode("base-tip-base")
        assert "base" in ctl.loop_mode_btn.text().lower()
