"""Clipper says its own name in the Windows task list.

Why an app names its processes, and why its own is the one it can only name for
the run after, is :mod:`app_support.process_identity`'s to say.  What is left
here is what only this repo can be wrong about: that the app makes the copy its
launcher starts it through, run against a throwaway venv rather than read off
``app.py``; that the launcher looks for that copy, and that the shortcut stamper
names the AppId the app sets -- both read off the file, because a ``.vbs`` or a
``.ps1`` really is a text file and really does contain the literal.
"""
from __future__ import annotations

from pathlib import Path

from app_support.process_identity import ProcessNamer
from app_support.process_identity_check import assert_the_app_names_its_process

from clipper.app import CLIPPER_APP_USER_MODEL_ID, _name_this_process

PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Clipper"
ROLE = "Clipper"

LAUNCHER = (PROJECT_DIR / "launch_clipper.vbs").read_text(encoding="utf-8")
STAMPER = (PROJECT_DIR / "set_shortcut_appid.ps1").read_text(encoding="utf-8")


def test_the_launcher_prefers_the_copy_named_for_this_app():
    expected = ProcessNamer(APP_NAME).exe_name("python.exe", ROLE)

    assert expected in LAUNCHER, f"the launcher does not look for {expected}"
    # Ahead of the plain interpreter, or it would never be reached.
    assert LAUNCHER.index(expected) < LAUNCHER.rindex(r"\.venv\Scripts\python.exe")


def test_the_launcher_still_works_before_any_run_has_named_it():
    """The naming runs one launch late, so a fresh checkout has no copy to
    find.  That must cost the name and nothing else."""
    assert r"\.venv\Scripts\python.exe" in LAUNCHER


def test_the_app_prepares_that_copy_for_next_time(tmp_path: Path):
    """From the console interpreter -- the launcher runs python.exe, redirecting
    the app's output into its log, so naming pythonw would leave a copy nothing
    ever starts.  Described as the app's name alone: one app with one window, so
    the row is its name, not its name twice.  Carrying the app's own mark.  And
    never taking a launch down: nothing to copy from costs the name and nothing
    else."""
    assert_the_app_names_its_process(
        _name_this_process, tmp_path, app_name=APP_NAME, role=ROLE,
        interpreter="python.exe", row=APP_NAME, icon=PROJECT_DIR / "clipper.ico")


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
