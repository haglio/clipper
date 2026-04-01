"""Launcher dialog — load existing session or create a new one."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from clipper.loop_modes import LOOP_MODES


class LauncherDialog(QDialog):
    """Session launcher replacing the Tkinter dialog."""

    def __init__(self, parent=None, *, last_session: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Clipper Launcher")
        self.setMinimumWidth(500)

        # Mode selection
        self.load_radio = QRadioButton("Load existing session")
        self.new_radio = QRadioButton("Create new session")
        self.load_radio.setChecked(True)

        # Load mode fields
        self.session_json_edit = QLineEdit(last_session)
        self.session_browse_btn = QPushButton("Browse...")
        self.session_browse_btn.clicked.connect(self._browse_session)

        load_row = QHBoxLayout()
        load_row.addWidget(QLabel("Session JSON:"))
        load_row.addWidget(self.session_json_edit)
        load_row.addWidget(self.session_browse_btn)

        # New mode fields
        self.session_name_edit = QLineEdit()
        self.video_file_edit = QLineEdit()
        self.video_browse_btn = QPushButton("Browse...")
        self.video_browse_btn.clicked.connect(self._browse_video)
        self.timestamp_edit = QLineEdit("00:00:00")
        self.seconds_edit = QLineEdit("5")
        self.loop_mode_combo = QComboBox()
        for mode in LOOP_MODES:
            self.loop_mode_combo.addItem(mode)

        video_row = QHBoxLayout()
        video_row.addWidget(QLabel("Video file:"))
        video_row.addWidget(self.video_file_edit)
        video_row.addWidget(self.video_browse_btn)

        # Buttons
        self.open_btn = QPushButton("Open")
        self.cancel_btn = QPushButton("Cancel")
        self.open_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.cancel_btn)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.load_radio)
        layout.addLayout(load_row)
        layout.addWidget(self.new_radio)
        layout.addWidget(QLabel("Session name:"))
        layout.addWidget(self.session_name_edit)
        layout.addLayout(video_row)
        layout.addWidget(QLabel("Timestamp (hh:mm:ss):"))
        layout.addWidget(self.timestamp_edit)
        layout.addWidget(QLabel("Seconds:"))
        layout.addWidget(self.seconds_edit)
        layout.addWidget(QLabel("Loop mode:"))
        layout.addWidget(self.loop_mode_combo)
        layout.addLayout(btn_row)

    def build_result(self) -> dict:
        """Build the result dict matching the legacy launcher_dialog() return shape."""
        if self.load_radio.isChecked():
            return {
                "ok": True,
                "mode": "load",
                "session_json": self.session_json_edit.text().strip(),
            }
        return {
            "ok": True,
            "mode": "new",
            "session_name": self.session_name_edit.text().strip(),
            "video_file": self.video_file_edit.text().strip(),
            "timestamp": self.timestamp_edit.text().strip(),
            "seconds": float(self.seconds_edit.text().strip() or "5"),
            "loop_mode": self.loop_mode_combo.currentText(),
        }

    def _browse_session(self) -> None:
        from clipper.paths import SESSIONS_DIR

        start_dir = str(SESSIONS_DIR) if SESSIONS_DIR.is_dir() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Session JSON", start_dir, "JSON Files (*.json)"
        )
        if path:
            self.session_json_edit.setText(path)

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)",
        )
        if path:
            self.video_file_edit.setText(path)
