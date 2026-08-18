"""Transport control buttons — speed, play/pause, export."""

from __future__ import annotations

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

import qtawesome as qta

from shared_ui.colors import TEXT_PRIMARY

# The chrome's own text color, so a glyph on a button matches the label beside
# it. It was its own near-white before, which is the sort of stray that leaves
# one app looking a shade off from the rest of the family.
_ICON_COLOR = TEXT_PRIMARY.name()
_ICON_SIZE = QSize(14, 14)


class ButtonBar(QWidget):
    """Horizontal row of transport control buttons."""

    speed_down_clicked = pyqtSignal()
    speed_up_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._icon_play = qta.icon("fa5s.play", color=_ICON_COLOR)
        self._icon_pause = qta.icon("fa5s.pause", color=_ICON_COLOR)

        self.speed_down_btn = QPushButton(qta.icon("fa5s.minus", color=_ICON_COLOR), "")
        self.speed_up_btn = QPushButton(qta.icon("fa5s.plus", color=_ICON_COLOR), "")
        self.play_pause_btn = QPushButton(self._icon_play, "")
        self.export_btn = QPushButton("export")

        for btn in (self.speed_down_btn, self.speed_up_btn, self.play_pause_btn):
            btn.setIconSize(_ICON_SIZE)

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
        self.play_pause_btn.setIcon(
            self._icon_pause if playing else self._icon_play
        )
