"""The launch smoke test: everything ``python -m clipper`` imports, imported.

The suite can be entirely green while the icon does nothing, and this is the
gap. ``main()`` reaches the GUI through an import *inside* the function, so a
break in ``clipper.gui.app`` -- the whole window -- never touches a test that
imports ``clipper.app`` and stops there. And every other test here runs under
``tests/conftest.py``, which force-resolves the ``clipper`` package before
collection precisely because the repo directory shares the package's name and
would otherwise win as a namespace shadow. The launcher has no such help: all
it does is cd here and run the venv's python, so what resolves at launch is not
what resolves under pytest.

So this drives the launch's import phase the way ``launch_clipper.vbs`` does: a
fresh interpreter, this repo as the working directory, no inherited
``PYTHONPATH``, and the committed example overlay standing in for the
git-ignored local one -- which is also what a public checkout and CI have.

The walk that reads those imports off the AST and the three assertions that
replay them are ``app_support.launch_smoke``: seven repos carried a copy of the
same 200 lines, drifting. What stays here is the half that is this app's --
which two files the launch executes, and how ``launch_clipper.vbs`` starts an
interpreter. A renamed ``ClipperApp`` is still the same dead icon as a syntax
error, and still fails here, because the replay is of whole ``from X import a,
b`` statements.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app_support.launch_smoke import (
    assert_an_unresolvable_import_is_caught,
    assert_every_import_resolves,
    assert_the_walk_reached,
    launch_imports,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "clipper"
LAUNCHER = REPO_ROOT / "launch_clipper.vbs"

# The two files ``python -m clipper`` runs. Every helper ``main()`` calls lives
# in ``app.py``, so between them they hold the whole launch sequence.
LAUNCH_FILES = (
    REPO_ROOT / PACKAGE / "__main__.py",
    REPO_ROOT / PACKAGE / "app.py",
)

# Reached only from inside ``main()``, so a module-level import test never saw
# them. Asserted present, so a walk that silently found nothing -- a renamed
# file, a parse that returned an empty tree -- cannot pass as a clean launch.
_REACHED_ONLY_FROM_INSIDE_MAIN = ("clipper.gui.app", "clipper.window_icons")


def _run_the_launchs_way(statements: list[str]) -> subprocess.CompletedProcess:
    """Run them the way ``launch_clipper.vbs`` runs the app.

    The launcher cds here and runs the venv's python with nothing else set, so
    the working directory is the whole path story -- any ``PYTHONPATH`` a
    developer or pytest happens to be carrying is dropped, because the icon does
    not get it.
    """
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["QT_QPA_PLATFORM"] = "offscreen"

    driver = "\n".join(
        [
            # Before anything that reads content at import time: a public
            # checkout has only the committed example, so that is what the
            # launch has to come up on.
            "import clipper.content as _content",
            "_content.LOCAL_CONTENT = _content.EXAMPLE_CONTENT",
            *statements,
        ]
    )
    return subprocess.run(
        [sys.executable, "-c", driver],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_the_launch_imports_everything_it_names():
    """Failing here means the icon does nothing: the traceback goes to
    ``state/clipper_launcher.log``, and no window ever appears."""
    assert_every_import_resolves(
        _run_the_launchs_way, launch_imports(PACKAGE, LAUNCH_FILES))


def test_the_walk_reaches_the_imports_buried_in_main():
    """The guard above is only worth anything if the walk found the lazy ones --
    which is where the window itself is."""
    assert_the_walk_reached(
        launch_imports(PACKAGE, LAUNCH_FILES), _REACHED_ONLY_FROM_INSIDE_MAIN)


def test_a_launch_import_that_cannot_resolve_fails_here():
    """A negative control: if the subprocess reported success regardless, every
    assertion above would pass vacuously and the guard would be decorative."""
    assert_an_unresolvable_import_is_caught(
        _run_the_launchs_way, launch_imports(PACKAGE, LAUNCH_FILES),
        "clipper.state")


def test_the_launcher_runs_the_package_from_this_repo_on_its_own_venv():
    """A python off PATH finds the repo directory as a namespace package instead
    of the editable install, and dies while importing -- before any window, with
    nothing on screen to say so. The cd is what this test's ``cwd`` mirrors, so
    a launcher that stopped doing it would leave this checking a fiction."""
    text = LAUNCHER.read_text(encoding="utf-8", errors="replace")

    assert ".venv\\Scripts\\python.exe" in text
    assert "-m clipper" in text
    assert "cd /d" in text


def test_the_launcher_keeps_what_a_failed_launch_wrote_to_its_console():
    """The launcher runs the app in a hidden window, so a crash during import
    writes its traceback to a console nobody sees. Redirecting it to
    ``state/clipper_launcher.log`` is what makes the next one readable."""
    text = LAUNCHER.read_text(encoding="utf-8", errors="replace")

    assert "clipper_launcher.log" in text
    assert "2>&1" in text
