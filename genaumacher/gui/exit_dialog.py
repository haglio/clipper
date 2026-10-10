"""Exit confirmation dialog — save, discard, or cancel."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ExitDialog(QDialog):
    """Modal dialog for unsaved-changes exit prompt."""

    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unsaved Changes")
        self.choice: str = self.CANCEL

        label = QLabel("Changes detected. Choose how to exit this session.")

        self.save_btn = QPushButton("Save and Exit")
        self.discard_btn = QPushButton("Exit without Save")
        self.cancel_btn = QPushButton("Cancel Exit")

        self.save_btn.clicked.connect(self._on_save)
        self.discard_btn.clicked.connect(self._on_discard)
        self.cancel_btn.clicked.connect(self._on_cancel)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.discard_btn)
        btn_row.addWidget(self.cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(btn_row)

    def _on_save(self) -> None:
        self.choice = self.SAVE
        self.accept()

    def _on_discard(self) -> None:
        self.choice = self.DISCARD
        self.accept()

    def _on_cancel(self) -> None:
        self.choice = self.CANCEL
        self.reject()
