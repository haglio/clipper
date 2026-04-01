"""Tests for clipper.gui.legend_widget — keycap shortcut legend."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.legend_widget import LegendWidget


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def widget():
    return LegendWidget()


class TestConstruction:
    def test_has_minimum_height(self, widget):
        assert widget.minimumHeight() >= 40

    def test_has_legend_rows(self, widget):
        assert len(widget.legend_rows) == 3

    def test_legend_rows_non_empty(self, widget):
        for row in widget.legend_rows:
            assert len(row) > 0
