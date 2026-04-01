"""Transport control buttons — speed, play/pause, export."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal


class ButtonBar(QWidget):
    """Horizontal row of transport control buttons."""

    speed_down_clicked = pyqtSignal()
    speed_up_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.speed_down_btn = QPushButton("-")
        self.speed_up_btn = QPushButton("+")
        self.play_pause_btn = QPushButton("Play")
        self.export_btn = QPushButton("Export")

        self.speed_down_btn.clicked.connect(self.speed_down_clicked)
        self.speed_up_btn.clicked.connect(self.speed_up_clicked)
        self.play_pause_btn.clicked.connect(self.play_pause_clicked)
        self.export_btn.clicked.connect(self.export_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.speed_down_btn)
        layout.addWidget(self.speed_up_btn)
        layout.addWidget(self.play_pause_btn)
        layout.addWidget(self.export_btn)

    def set_playing(self, playing: bool) -> None:
        self.play_pause_btn.setText("Pause" if playing else "Play")
