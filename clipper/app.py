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


def _name_this_process() -> None:
    """Leave ``launch_clipper.vbs`` an interpreter that says "Clipper" next time.

    Windows takes what it shows about a process from the file it was started
    from -- the Details tab's name, the Processes tab's description, the icon
    beside it -- so a plain interpreter puts Clipper in the task list as one more
    anonymous "Python".  That costs nothing until something strands a process,
    and then the task list is the only way back and cannot say which row is safe
    to end.

    Naming this process on the way in is the one thing that cannot be done:
    writing the copy takes the very interpreter being named.  So each run makes
    it for the run after and the launcher picks it up, which costs one launch,
    once.  A checkout that has never started launches exactly as it used to.
    """
    try:
        from pathlib import Path as _Path

        from app_support.process_identity import ProcessNamer

        icon = _Path(__file__).resolve().parent.parent / "clipper.ico"
        ProcessNamer("Clipper", icon=icon).prepare_launcher(
            "Clipper", _Path(sys.executable).with_name("python.exe"))
    except Exception:
        pass  # Cosmetic: costs a name in the task list, never a launch.


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
