"""Timeline manipulation buttons — extend, contract, shift, mark, wrap, loop mode."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal


class TimelineControls(QWidget):
    """Collection of buttons for manipulating timeline bounds and marks."""

    extend_left_clicked = pyqtSignal()
    contract_left_clicked = pyqtSignal()
    extend_right_clicked = pyqtSignal()
    contract_right_clicked = pyqtSignal()
    shift_left_clicked = pyqtSignal()
    shift_right_clicked = pyqtSignal()
    mark_in_clicked = pyqtSignal()
    mark_out_clicked = pyqtSignal()
    wrap_clicked = pyqtSignal()
    loop_mode_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # Bound adjustment buttons
        self.extend_left_btn = QPushButton("<")
        self.contract_left_btn = QPushButton(">")
        self.contract_right_btn = QPushButton("<")
        self.extend_right_btn = QPushButton(">")

        # Shift buttons
        self.shift_left_btn = QPushButton("<")
        self.shift_right_btn = QPushButton(">")

        # Mark buttons
        self.mark_in_btn = QPushButton("[")
        self.mark_out_btn = QPushButton("]")

        # Wrap and loop mode
        self.wrap_btn = QPushButton("wrap")
        self.loop_mode_btn = QPushButton("base-tip-base")

        # Wire signals
        self.extend_left_btn.clicked.connect(self.extend_left_clicked)
        self.contract_left_btn.clicked.connect(self.contract_left_clicked)
        self.extend_right_btn.clicked.connect(self.extend_right_clicked)
        self.contract_right_btn.clicked.connect(self.contract_right_clicked)
        self.shift_left_btn.clicked.connect(self.shift_left_clicked)
        self.shift_right_btn.clicked.connect(self.shift_right_clicked)
        self.mark_in_btn.clicked.connect(self.mark_in_clicked)
        self.mark_out_btn.clicked.connect(self.mark_out_clicked)
        self.wrap_btn.clicked.connect(self.wrap_clicked)
        self.loop_mode_btn.clicked.connect(self.loop_mode_clicked)

        # Layout
        bounds_row = QHBoxLayout()
        bounds_row.addWidget(self.extend_left_btn)
        bounds_row.addWidget(self.contract_left_btn)
        bounds_row.addStretch()
        bounds_row.addWidget(self.shift_left_btn)
        bounds_row.addWidget(self.mark_in_btn)
        bounds_row.addWidget(self.mark_out_btn)
        bounds_row.addWidget(self.shift_right_btn)
        bounds_row.addStretch()
        bounds_row.addWidget(self.contract_right_btn)
        bounds_row.addWidget(self.extend_right_btn)

        mode_row = QHBoxLayout()
        mode_row.addStretch()
        mode_row.addWidget(self.wrap_btn)
        mode_row.addWidget(self.loop_mode_btn)
        mode_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bounds_row)
        layout.addLayout(mode_row)

    def set_loop_mode(self, mode: str) -> None:
        self.loop_mode_btn.setText(mode)
