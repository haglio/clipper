"""What launch_clipper.vbs runs, asked of the launcher under the real script host.

The launcher is rendered from its spec in pyproject.toml by app_support.launcher,
whose own tests hold what every launcher does: the venv's interpreter and never
one off PATH, nothing on PYTHONPATH, Option Explicit, a dialog naming a missing
venv.  What is Clipper's is asked of this one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app_support.launcher import assert_launchers_match_their_specs, dry_run

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "launch_clipper.vbs"

on_windows = pytest.mark.skipif(sys.platform != "win32", reason="the Windows script host")


def test_the_launcher_is_where_the_pinned_shortcut_points():
    assert LAUNCHER.is_file()


def test_the_launcher_is_what_its_spec_renders():
    assert_launchers_match_their_specs(REPO_ROOT)


@on_windows
def test_the_launcher_runs_the_package_from_this_checkout_on_its_venv():
    """A python off PATH finds the repo directory as a namespace package instead
    of the editable install, and dies while importing -- before any window."""
    report = dry_run(LAUNCHER)

    assert Path(report.value("interpreter")).parent == REPO_ROOT / ".venv" / "Scripts"
    assert Path(report.value("directory")) == REPO_ROOT
    assert report.value("arguments") == "-m clipper"


@on_windows
def test_a_launch_that_dies_importing_leaves_its_traceback_in_state():
    report = dry_run(LAUNCHER)

    assert Path(report.value("log")) == REPO_ROOT / "state" / "clipper_launcher.log"


@on_windows
def test_a_branch_preview_runs_its_own_checkout_on_the_primary_checkouts_venv():
    report = dry_run(REPO_ROOT / "launch_preview_branch.vbs")

    primary = REPO_ROOT.parents[2]
    assert Path(report.value("interpreter")) == primary / ".venv" / "Scripts" / "python.exe"
    assert Path(report.value("directory")) == REPO_ROOT
    assert report.value("arguments") == "-m clipper"
    overlay = "content.local.json"
    assert report.value("copy") == f"{primary / overlay} > {REPO_ROOT / overlay}"
