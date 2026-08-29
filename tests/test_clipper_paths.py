"""Tests for clipper.paths."""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from clipper import paths
from clipper.paths import ensure_runtime_dirs, library_is_configured


# The five directories the app writes into. Named here rather than read out of
# the function, so dropping one from the loop is a red test and not a folder
# that silently stops being made.
_RUNTIME_DIRS = (
    "SESSIONS_DIR",
    "RAW_CLIPS_DIR",
    "CLIPS_DIR",
    "VR_CLIPS_DIR",
    "AUDIO_DIR",
)


def _constants_ensure_runtime_dirs_creates() -> set[str]:
    """The module constants the function's own loop walks."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(ensure_runtime_dirs)))
    return {
        leaf.id
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        for leaf in ast.walk(node.iter)
        if isinstance(leaf, ast.Name)
    }


def _with_a_local_overlay(tmp_path: Path, monkeypatch) -> None:
    """Stand in the ``content.local.json`` a machine with a real library has."""
    local = tmp_path / "content.local.json"
    local.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "LOCAL_CONTENT", local)


@pytest.fixture()
def runtime_dirs(tmp_path: Path, monkeypatch):
    """Point every directory ``ensure_runtime_dirs`` creates at tmp_path.

    Four of the six the loop then had were patched and two were not, so simply
    running the suite created ``<suite-root>/videos/genau/vr_clips`` and
    ``.../frames`` for real -- a literal ``C:`` tree inside the checkout on a
    developer machine, and the live media library on the Windows machines the
    app runs on. The fixture redirects the constants named above *and* any the
    function iterates that are not, so a sixth cannot escape while its test is
    being written.
    """
    for name in set(_RUNTIME_DIRS) | _constants_ensure_runtime_dirs_creates():
        monkeypatch.setattr(paths, name, tmp_path / name.lower())
    _with_a_local_overlay(tmp_path, monkeypatch)
    return {name: tmp_path / name.lower() for name in _RUNTIME_DIRS}


class TestEnsureRuntimeDirs:
    def test_creates_every_directory_the_app_writes_into(self, runtime_dirs):
        ensure_runtime_dirs()

        missing = sorted(name for name, path in runtime_dirs.items() if not path.is_dir())
        assert missing == []

    def test_the_directories_it_creates_are_the_ones_named_here(self):
        """A sixth added to the loop needs a line above, or it escapes."""
        assert _constants_ensure_runtime_dirs_creates() == set(_RUNTIME_DIRS)

    def test_a_second_run_keeps_what_the_first_one_left(self, runtime_dirs):
        ensure_runtime_dirs()
        (runtime_dirs["SESSIONS_DIR"] / "demo.json").write_text("{}", encoding="utf-8")

        ensure_runtime_dirs()

        assert (runtime_dirs["SESSIONS_DIR"] / "demo.json").read_text(encoding="utf-8") == "{}"
        assert all(path.is_dir() for path in runtime_dirs.values())

    def test_it_creates_the_parents_a_fresh_machine_has_none_of(self, tmp_path, monkeypatch):
        deep = tmp_path / "videos" / "genau" / "clips"
        for name in set(_RUNTIME_DIRS) | _constants_ensure_runtime_dirs_creates():
            monkeypatch.setattr(paths, name, deep if name == "CLIPS_DIR" else tmp_path / name.lower())
        _with_a_local_overlay(tmp_path, monkeypatch)

        ensure_runtime_dirs()

        assert deep.is_dir()


class TestACheckoutWithNoLocalOverlay:
    """The committed example's ``suite_root`` is a placeholder, not a library.

    ``C:/path/to/suite-root`` is a *relative* path on POSIX, so deriving the
    library folders from it made a literal ``C:`` tree inside the checkout; on
    Windows the same string is absolute and made ``C:\\path\\to\\suite-root`` on
    the system drive. Neither is anywhere clipper should write, and the next
    export would have put real media there -- inside the repo, one ``git add``
    from a public commit.
    """

    def test_a_local_overlay_is_what_makes_a_library(self, tmp_path, monkeypatch):
        local = tmp_path / "content.local.json"
        local.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(paths, "LOCAL_CONTENT", local)

        assert library_is_configured() is True

    def test_without_one_there_is_no_library(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "LOCAL_CONTENT", tmp_path / "content.local.json")

        assert library_is_configured() is False

    def test_the_repos_own_directories_are_still_made(self, runtime_dirs, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "LOCAL_CONTENT", tmp_path / "absent.json")

        ensure_runtime_dirs()

        assert runtime_dirs["SESSIONS_DIR"].is_dir()
        assert runtime_dirs["RAW_CLIPS_DIR"].is_dir()

    def test_no_library_directory_is_made(self, runtime_dirs, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "LOCAL_CONTENT", tmp_path / "absent.json")

        ensure_runtime_dirs()

        made = [name for name in ("CLIPS_DIR", "VR_CLIPS_DIR", "AUDIO_DIR")
                if runtime_dirs[name].is_dir()]
        assert made == []
