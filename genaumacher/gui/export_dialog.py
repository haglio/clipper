"""Export progress dialog — a bar per stage, and a Close that waits for the end."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ExportDialog(QDialog):
    """Modal dialog showing export progress for clip, fix, and audio stages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exporting")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowCloseButtonHint)
        self.setFixedWidth(450)

        self.stage_label = QLabel("Preparing export...")
        self.error_label = QLabel("")

        self.clip_bar = QProgressBar()
        self.fix_bar = QProgressBar()
        self.audio_bar = QProgressBar()

        for bar in (self.clip_bar, self.fix_bar, self.audio_bar):
            bar.setRange(0, 100)
            bar.setValue(0)

        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stage_label)
        layout.addWidget(QLabel("Raw clip:"))
        layout.addWidget(self.clip_bar)
        layout.addWidget(QLabel("Normalize / fix:"))
        layout.addWidget(self.fix_bar)
        layout.addWidget(QLabel("Audio extract:"))
        layout.addWidget(self.audio_bar)
        layout.addWidget(self.error_label)
        layout.addWidget(self.close_btn)

    def set_clip_progress(self, frac: float) -> None:
        self.clip_bar.setValue(int(frac * 100))

    def set_fix_progress(self, frac: float) -> None:
        self.fix_bar.setValue(int(frac * 100))

    def set_audio_progress(self, frac: float) -> None:
        self.audio_bar.setValue(int(frac * 100))

    def set_stage(self, text: str) -> None:
        self.stage_label.setText(text)

    def set_error(self, text: str) -> None:
        self.error_label.setText(text)

    def set_done(self, success: bool) -> None:
        self.close_btn.setEnabled(True)
        if success:
            self.stage_label.setText("Export complete.")
        else:
            self.stage_label.setText("Export failed.")
