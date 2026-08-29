"""Clipper says its own name in the Windows task list.

Windows takes what it shows about a process -- the Details tab's name, the
Processes tab's description, the icon beside it -- from the file the process was
started from, so a plain interpreter puts Clipper in the task list as one more
anonymous "Python".  That costs nothing until something strands a process, and
then the task list is the only way back and cannot say which row is safe to end,
among half a dozen identical ones belonging to different apps.

``app_support.process_identity`` makes a copy of the interpreter named,
described and marked for this app.  Naming this process on the way in is the one
thing that cannot be done -- writing the copy takes the very interpreter being
named -- so each run prepares it for the run after and the launcher picks it up.
Both halves are asserted: a launcher that never looks, or an app that never
prepares, leaves the app anonymous for good.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from app_support.process_identity import ProcessNamer

from clipper.app import CLIPPER_APP_USER_MODEL_ID, _name_this_process

PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Clipper"
ROLE = "Clipper"

# The launcher is VBScript: it cannot be run here, so its two guarantees are
# read out of the file.  Everything on the Python side below is driven instead.
LAUNCHER = (PROJECT_DIR / "launch_clipper.vbs").read_text(encoding="utf-8")
STAMPER = (PROJECT_DIR / "set_shortcut_appid.ps1").read_text(encoding="utf-8")


def test_the_launcher_prefers_the_copy_named_for_this_app():
    expected = ProcessNamer(APP_NAME).exe_name("python.exe", ROLE)

    assert expected in LAUNCHER, f"the launcher does not look for {expected}"
    # Ahead of the plain interpreter, or it would never be reached.
    assert LAUNCHER.index(expected) < LAUNCHER.rindex(r"\.venv\Scripts\python.exe")


def test_the_launcher_still_works_before_any_run_has_named_it():
    """The naming runs one launch behind, so a fresh checkout has no copy to
    find.  That must cost the name and nothing else."""
    assert r"\.venv\Scripts\python.exe" in LAUNCHER


def test_the_app_prepares_that_copy_for_next_time():
    """Driven, not read: the source used to be slurped and searched for
    `_name_this_process()`, `ProcessNamer("Clipper"` and `"Clipper"`, which
    passes for a helper that is called and broken, and fails for one that was
    renamed and works."""
    namer = MagicMock()

    with patch("app_support.process_identity.ProcessNamer", return_value=namer) as cls:
        _name_this_process()

    assert cls.call_args.args == (APP_NAME,)
    (role, interpreter) = namer.prepare_launcher.call_args.args
    assert role == ROLE
    assert namer.prepare_launcher.call_count == 1
    assert interpreter == Path(sys.executable).with_name("python.exe"), (
        "the launcher runs python.exe -- it redirects the app's output into its "
        "log -- so naming pythonw would leave a copy nothing ever starts"
    )


def test_the_row_reads_as_the_app_and_nothing_more():
    # One app with one window, so the row is its name, not its name twice.
    assert ProcessNamer(APP_NAME).description(ROLE) == APP_NAME


def test_it_stamps_its_own_mark():
    namer = MagicMock()

    with patch("app_support.process_identity.ProcessNamer", return_value=namer) as cls:
        _name_this_process()

    icon = cls.call_args.kwargs["icon"]
    assert icon.name == "clipper.ico"
    assert icon.is_file()


def test_naming_never_takes_a_launch_down():
    """A read-only venv or an antivirus hold must cost the name in the task list
    and nothing else."""
    with patch("app_support.process_identity.ProcessNamer",
               side_effect=OSError("the venv is read-only")) as refusing:
        _name_this_process()  # must not raise

    assert refusing.called, "it swallowed the failure without reaching the naming"

    namer = MagicMock()
    namer.prepare_launcher.side_effect = PermissionError("held open")
    with patch("app_support.process_identity.ProcessNamer", return_value=namer):
        _name_this_process()  # nor here

    namer.prepare_launcher.assert_called_once()


def test_the_shortcut_stamper_names_the_app_id_the_app_sets():
    """`set_shortcut_appid.ps1` and clipper/app.py must agree on the AppId.

    The script is run by hand, once, after the shortcut is made: no CI step, no
    launcher and no test called it, so nothing would have noticed the two
    drifting. A shortcut stamped with one AppId and a process setting another
    gives Windows two things to group and the taskbar a second, blank button.

    A text assertion because a .ps1 is a text file that really does contain the
    literal -- the same carve-out the launcher assertions above sit under.
    """
    assert f"$AppId = '{CLIPPER_APP_USER_MODEL_ID}'" in STAMPER
