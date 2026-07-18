from __future__ import annotations

import logging
import sys

from app_support.logging_utils import configure_logging, install_exception_logging

from .config import PROJECT_DIR
from .session_launch import launch_state

CLIPPER_APP_USER_MODEL_ID = "FunTime.Clipper"


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        _ = set_app_id(CLIPPER_APP_USER_MODEL_ID)
    except Exception:
        pass


def _init_logger() -> logging.Logger:
    log_path = PROJECT_DIR / "state" / "clipper.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = configure_logging("clipper", log_path, console=False)
    install_exception_logging(logger)
    return logger


def main() -> int:
    _set_windows_app_user_model_id()
    logger = _init_logger()
    try:
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QApplication, QMessageBox

        _app = QApplication.instance() or QApplication(sys.argv)
        # Set icon early so the launcher dialog inherits it.
        from .window_icons import clipper_icon_path

        _ico = clipper_icon_path()
        if _ico.exists():
            _app.setWindowIcon(QIcon(str(_ico)))
        state = launch_state()
        if state is None:
            return 0

        from .gui.app import ClipperApp

        clipper_app = ClipperApp(state)
        return clipper_app.run()
    except SystemExit:
        raise
    except Exception as exc:
        logger.exception("Clipper crashed")
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox

            _app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Clipper", f"ERROR: {exc}")
        except Exception:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
