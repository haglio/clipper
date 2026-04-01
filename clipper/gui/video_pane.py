"""Video frame display widget — shows a single QImage, centered."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QWidget

from shared_ui.colors import BG_SECONDARY, BORDER_SUBTLE


class VideoPane(QWidget):
    """Displays a single video frame as a QImage."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._image: QImage | None = None
        self.setMinimumSize(320, 240)
        self.setStyleSheet(
            f"border: 1px solid {BORDER_SUBTLE.name()}; background: {BG_SECONDARY.name()};"
        )

    def current_image(self) -> QImage | None:
        return self._image

    def set_frame(self, image: QImage | None) -> None:
        self._image = image
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), BG_SECONDARY)

        if self._image is not None:
            # Center the image in the widget
            iw, ih = self._image.width(), self._image.height()
            x = (self.width() - iw) / 2
            y = (self.height() - ih) / 2
            p.drawImage(QRectF(x, y, iw, ih), self._image)

        p.end()
