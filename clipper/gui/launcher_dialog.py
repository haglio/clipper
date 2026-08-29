"""Launcher dialog — load existing session or create a new one."""

from __future__ import annotations

from pathlib import PureWindowsPath

from PyQt6.QtWidgets import (
    QCheckBox,
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

from clipper.content import load_content
from clipper.loop_modes import LOOP_MODES

# The library root is private; it comes from the content overlay.
VR_VIDEO_DIR = PureWindowsPath(load_content()["suite_root"]) / "videos" / "videos" / "VR"


class LauncherDialog(QDialog):
    """Chooses between loading a saved session and creating a new one."""

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
        self.vr_checkbox = QCheckBox("VR")
        self.video_file_edit.textChanged.connect(self._on_video_path_changed)

        video_row = QHBoxLayout()
        video_row.addWidget(QLabel("Video file:"))
        video_row.addWidget(self.video_file_edit)
        video_row.addWidget(self.video_browse_btn)

        # Buttons
        self.clip_whole_btn = QPushButton("Clip whole vid...")
        self.clip_whole_btn.clicked.connect(self._browse_clip_whole)
        self.open_btn = QPushButton("Open")
        self.cancel_btn = QPushButton("Cancel")
        self.open_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        self._clip_whole_file: str = ""

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.clip_whole_btn)
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
        layout.addWidget(self.vr_checkbox)
        layout.addLayout(btn_row)

    def build_result(self) -> dict:
        """What the caller launches from: ``ok``, a ``mode``, and that mode's fields.

        ``clip_whole`` carries a video_file; ``load`` a session_json; ``new`` the
        seven fields the form collects.
        """
        if self._clip_whole_file:
            return {
                "ok": True,
                "mode": "clip_whole",
                "video_file": self._clip_whole_file,
            }
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
            "vr": self.vr_checkbox.isChecked(),
        }

    def _browse_session(self) -> None:
        from clipper.paths import SESSIONS_DIR

        start_dir = str(SESSIONS_DIR) if SESSIONS_DIR.is_dir() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Session JSON", start_dir, "JSON Files (*.json)"
        )
        if path:
            self.session_json_edit.setText(path)

    def _on_video_path_changed(self) -> None:
        path = PureWindowsPath(self.video_file_edit.text().strip())
        self.vr_checkbox.setChecked(path.is_relative_to(VR_VIDEO_DIR))

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)",
        )
        if path:
            self.video_file_edit.setText(path)

    def _browse_clip_whole(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video to Clip Whole",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)",
        )
        if path:
            self._clip_whole_file = path
            self.accept()
