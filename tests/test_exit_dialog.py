"""Tests for clipper.gui.exit_dialog — exit confirmation dialog."""

from __future__ import annotations


import pytest

from clipper.gui.exit_dialog import ExitDialog


@pytest.fixture()
def dialog():
    return ExitDialog()


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
