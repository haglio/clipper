"""Tests for clipper.paths."""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
from pathlib import Path

import pytest

from clipper import paths
from clipper.paths import (
    FORBIDDEN_NAME_CHARS,
    ensure_runtime_dirs,
    library_is_configured,
    sanitize_name,
)

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


def _with_a_real_library(tmp_path: Path, monkeypatch) -> None:
    """A ``suite_root`` of this machine's own, as a configured overlay gives."""
    monkeypatch.setattr(paths, "_SUITE_ROOT", tmp_path / "library")


@pytest.fixture
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
    _with_a_real_library(tmp_path, monkeypatch)
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
        _with_a_real_library(tmp_path, monkeypatch)

        ensure_runtime_dirs()

        assert deep.is_dir()


class TestAMachineWithNoLibraryYet:
    """The committed example's ``suite_root`` is a placeholder, not a library.

    ``C:/path/to/suite-root`` is a *relative* path on POSIX, so deriving the
    library folders from it made a literal ``C:`` tree inside the checkout; on
    Windows the same string is absolute and made ``C:\\path\\to\\suite-root`` on
    the system drive. Neither is anywhere clipper should write, and the next
    export would have put real media there -- inside the repo, one ``git add``
    from a public commit.
    """

    def test_a_suite_root_of_its_own_is_what_makes_a_library(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "_SUITE_ROOT", tmp_path / "library")

        assert library_is_configured() is True

    def test_the_placeholder_is_not_a_library(self, monkeypatch):
        monkeypatch.setattr(paths, "_SUITE_ROOT", paths._PLACEHOLDER_SUITE_ROOT)

        assert library_is_configured() is False

    def test_an_unedited_copy_of_the_example_is_not_a_library_either(self, tmp_path, monkeypatch):
        """Setting a machine up is copy-then-edit, and this is between the two.

        Asking whether a ``content.local.json`` exists answers yes here, which
        is how the ``C:`` tree came back while a guard was supposedly stopping it.
        """
        local = tmp_path / "content.local.json"
        local.write_text(paths.EXAMPLE_CONTENT.read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(
            paths, "_SUITE_ROOT", Path(json.loads(local.read_text(encoding="utf-8"))["suite_root"])
        )

        assert library_is_configured() is False

    def test_the_repos_own_directories_are_still_made(self, runtime_dirs, monkeypatch):
        monkeypatch.setattr(paths, "_SUITE_ROOT", paths._PLACEHOLDER_SUITE_ROOT)

        ensure_runtime_dirs()

        assert runtime_dirs["SESSIONS_DIR"].is_dir()
        assert runtime_dirs["RAW_CLIPS_DIR"].is_dir()

    def test_no_library_directory_is_made(self, runtime_dirs, monkeypatch):
        monkeypatch.setattr(paths, "_SUITE_ROOT", paths._PLACEHOLDER_SUITE_ROOT)

        ensure_runtime_dirs()

        made = [name for name in ("CLIPS_DIR", "VR_CLIPS_DIR", "AUDIO_DIR")
                if runtime_dirs[name].is_dir()]
        assert made == []


class TestSanitizeName:
    def test_clean_name_unchanged(self):
        assert sanitize_name("clean name") == "clean name"

    def test_strips_leading_trailing_spaces(self):
        assert sanitize_name("  hello  ") == "hello"

    @pytest.mark.parametrize("forbidden", list(FORBIDDEN_NAME_CHARS))
    def test_every_character_a_filename_cannot_hold_becomes_an_underscore(self, forbidden):
        """Walks the module's own list, so adding a character adds a case."""
        assert sanitize_name(f"take{forbidden}one") == "take_one"

    def test_the_list_is_the_nine_windows_refuses(self):
        """One literal, so removing a character from the list is red too."""
        assert sanitize_name('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"

    def test_strips_trailing_dots(self):
        result = sanitize_name("filename.")
        assert not result.endswith(".")

    def test_a_name_of_only_spaces_becomes_the_empty_string(self):
        assert sanitize_name("   ") == ""
