from __future__ import annotations

import logging
import sys

from app_support.logging_utils import configure_logging, install_exception_logging
from app_support.process_identity import ProcessNamer
from app_support.win32 import set_app_user_model_id

from .paths import PROJECT_DIR
from .session_launch import launch_state

CLIPPER_APP_USER_MODEL_ID = "FunTime.Clipper"


def _set_windows_app_user_model_id() -> None:
    """Claim the identity the pinned shortcut carries, before any window exists.

    Cosmetic: a window under the interpreter's icon is still a window, so a
    refusal is logged and the launch goes on.
    """
    if sys.platform != "win32":
        return
    try:
        set_app_user_model_id(CLIPPER_APP_USER_MODEL_ID)
    except OSError:
        logging.getLogger(__name__).debug(
            "Could not set the AppUserModelID", exc_info=True)


def _init_logger() -> logging.Logger:
    log_path = PROJECT_DIR / "state" / "clipper.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = configure_logging("clipper", log_path, console=False)
    install_exception_logging(logger)
    return logger


def _name_this_process() -> None:
    """Leave ``launch_clipper.vbs`` an interpreter that says "Clipper" next
    time.  The console interpreter, because that is the one the launcher runs --
    it redirects the app's output into its log.  Why it is one launch behind, and
    why it can never cost the launch: :meth:`ProcessNamer.name_this_process`."""
    ProcessNamer("Clipper", icon=PROJECT_DIR / "clipper.ico").name_this_process(
        "Clipper", interpreter="python.exe")


def main() -> int:
    _set_windows_app_user_model_id()
    _name_this_process()
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
    except Exception as exc:
        logger.exception("Clipper crashed")
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox

            _app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Clipper", f"ERROR: {exc}")
        except Exception:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
