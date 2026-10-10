from __future__ import annotations

import logging
import sys

from app_support.logging_utils import configure_logging, install_exception_logging
from app_support.process_identity import ProcessNamer
from app_support.win32 import set_app_user_model_id, stamp_pinned_shortcuts
from shared_ui.preview import Preview, preview_of, taskbar_identity, window_title
from shared_ui.preview_icon import app_icon

from .interpolator_environment import complaints
from .paths import PROJECT_DIR
from .session_launch import launch_state
from .window_icons import genaumacher_icon_path

APP_USER_MODEL_ID = "FunTime.Genaumacher"


def _set_windows_app_user_model_id(preview: Preview | None) -> None:
    """Claim the identity the pinned shortcut carries, and stamp the pin with it,
    before any window exists.

    Cosmetic: a window under the interpreter's icon is still a window, so a
    refusal is logged and the launch goes on.
    """
    if sys.platform != "win32":
        return
    try:
        set_app_user_model_id(taskbar_identity(APP_USER_MODEL_ID, preview))
    except OSError:
        logging.getLogger(__name__).debug(
            "Could not set the AppUserModelID", exc_info=True)
    stamp_pinned_shortcuts(APP_USER_MODEL_ID, ["Genaumacher"])


def _init_logger() -> logging.Logger:
    log_path = PROJECT_DIR / "state" / "genaumacher.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = configure_logging("genaumacher", log_path, console=False)
    install_exception_logging(logger)
    return logger


def _report_interpolator_environment(logger: logging.Logger) -> None:
    """Say on the way up when this checkout's frame interpolator cannot be used.

    Here rather than in the suite: the merge gate fetches the interpolator on
    purpose, so a test of this could only ever pass there, while the machine
    that makes the clips -- which may never have fetched -- got the geometric
    seam and no word.  It lands in ``state/genaumacher.log``.
    """
    for said in complaints():
        logger.warning("Frame interpolator: %s", said)


def _name_this_process() -> None:
    """Leave ``launch_genaumacher.vbs`` an interpreter that says "Genaumacher" next
    time.  The console interpreter, because that is the one the launcher runs --
    it redirects the app's output into its log.  Why it is one launch late, and
    why it can never cost the launch: :meth:`ProcessNamer.name_this_process`."""
    ProcessNamer("Genaumacher", icon=PROJECT_DIR / "genaumacher.ico").name_this_process(
        "Genaumacher", interpreter="python.exe")


def main() -> int:
    preview = preview_of(PROJECT_DIR)
    _set_windows_app_user_model_id(preview)
    _name_this_process()
    logger = _init_logger()
    _report_interpolator_environment(logger)
    try:
        # Local: the toolkit loads when a window is wanted, and the handler
        # below is what turns a failure to load it into a readable message.
        from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: PLC0415

        _app = QApplication.instance() or QApplication(sys.argv)
        # Set icon early so the launcher dialog inherits it.
        _app.setWindowIcon(app_icon(genaumacher_icon_path(), preview))
        state = launch_state()
        if state is None:
            return 0

        # Local: the editor window, and the toolkit under it, only once the
        # launcher has said there is a session to open.
        from .gui.app import GenaumacherApp  # noqa: PLC0415

        genaumacher_app = GenaumacherApp(state, preview=preview)
        return genaumacher_app.run()
    except Exception as exc:
        logger.exception("Genaumacher crashed")
        try:
            # Local: this is the handler for a failure that may BE the
            # toolkit's import, so it asks for it rather than assuming it.
            from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: PLC0415

            _app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, window_title("Genaumacher", preview), f"ERROR: {exc}")
        except Exception:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
