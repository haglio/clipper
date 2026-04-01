"""Tests for clipper.gui.exit_dialog — exit confirmation dialog."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.exit_dialog import ExitDialog


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def dialog():
    return ExitDialog()


class TestConstruction:
    def test_has_three_buttons(self, dialog):
        assert dialog.save_btn is not None
        assert dialog.discard_btn is not None
        assert dialog.cancel_btn is not None

    def test_result_constants(self, dialog):
        assert ExitDialog.SAVE == "save"
        assert ExitDialog.DISCARD == "discard"
        assert ExitDialog.CANCEL == "cancel"


class TestButtonResults:
    def test_save_sets_result(self, dialog):
        dialog.save_btn.click()
        assert dialog.choice == ExitDialog.SAVE

    def test_discard_sets_result(self, dialog):
        dialog.discard_btn.click()
        assert dialog.choice == ExitDialog.DISCARD

    def test_cancel_sets_result(self, dialog):
        dialog.cancel_btn.click()
        assert dialog.choice == ExitDialog.CANCEL
