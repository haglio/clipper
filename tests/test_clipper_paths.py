"""Tests for clipper.paths."""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from clipper import content, paths
from clipper.paths import (
    FORBIDDEN_NAME_CHARS,
    audio_dir,
    clips_dir,
    ensure_runtime_dirs,
    library_is_configured,
    sanitize_name,
    vr_clips_dir,
)

# The five directories the app writes into, by the name the function reaches
# them under -- two module constants inside the checkout, three accessors that
# ask the overlay where the library is. Named here rather than read out of the
# function, so dropping one from the loop is a red test and not a folder that
# silently stops being made.
_RUNTIME_DIRS = (
    "SESSIONS_DIR",
    "RAW_CLIPS_DIR",
    "clips_dir",
    "vr_clips_dir",
    "audio_dir",
)


def _names_ensure_runtime_dirs_creates() -> set[str]:
    """The names the function's own loops walk."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(ensure_runtime_dirs)))
    return {
        leaf.id
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        for leaf in ast.walk(node.iter)
        if isinstance(leaf, ast.Name)
    }


@pytest.fixture
def checkout_dirs(tmp_path: Path, monkeypatch):
    """The two directories that live inside the checkout, pointed at tmp_path."""
    names = ("SESSIONS_DIR", "RAW_CLIPS_DIR")
    for name in names:
        monkeypatch.setattr(paths, name, tmp_path / name.lower())
    return {name: tmp_path / name.lower() for name in names}


@pytest.fixture
def runtime_dirs(tmp_path: Path, content_overlay, checkout_dirs):
    """Everything ``ensure_runtime_dirs`` creates, under tmp_path.

    Four of the six it had were patched and two were not, so simply running the
    suite created ``<suite-root>/videos/genau/vr_clips`` and ``.../frames`` for
    real -- a literal ``C:`` tree inside the checkout on a developer machine,
    and the live media library on the Windows machines the app runs on.  The
    library folders now move together, by giving the overlay a suite root of its
    own, so a fourth one added to that loop lands under tmp_path without a line
    here; a third checkout constant would escape, which is what the guard test
    below is for.
    """
    content_overlay({"suite_root": str(tmp_path / "library")})
    genau = tmp_path / "library" / "videos" / "genau"
    return {
        **checkout_dirs,
        "clips_dir": genau / "clips",
        "vr_clips_dir": genau / "vr_clips",
        "audio_dir": genau / "audio",
    }


class TestWhereTheLibraryFoldersAre:
    """Read when asked, not when imported.

    ``clipper.paths`` used to derive them at import, so the folders an export
    wrote into were whichever overlay happened to be on disk when the package
    was first imported, and a test could only move them by patching the
    constants by name.
    """

    def test_the_clip_folder_hangs_off_the_suite_root_the_overlay_names(
        self, tmp_path: Path, content_overlay
    ):
        content_overlay({"suite_root": "D:/example-suite"})

        assert clips_dir() == Path("D:/example-suite/videos/genau/clips")

    def test_the_three_of_them_sit_together_under_one_folder(self, content_overlay):
        content_overlay({"suite_root": "D:/example-suite"})

        parents = {clips_dir().parent, vr_clips_dir().parent, audio_dir().parent}

        assert parents == {Path("D:/example-suite/videos/genau")}
        assert {clips_dir().name, vr_clips_dir().name, audio_dir().name} == {
            "clips", "vr_clips", "audio",
        }

    def test_an_overlay_written_after_the_import_is_the_one_that_answers(
        self, tmp_path: Path, content_overlay
    ):
        """The proof that the read is at the call and not at the import: this
        overlay did not exist when ``clipper.paths`` was first imported.
        """
        content_overlay({"suite_root": str(tmp_path / "written just now")})

        assert clips_dir().is_relative_to(tmp_path / "written just now")

    def test_an_overlay_with_no_suite_root_says_so_and_names_the_file(
        self, content_overlay
    ):
        local = content_overlay({"nau_status_file": "D:/example-suite/nau_status.txt"})

        with pytest.raises(LookupError, match="suite_root"):
            clips_dir()

        with pytest.raises(LookupError, match=str(local.name)):
            clips_dir()


class TestEnsureRuntimeDirs:
    def test_creates_every_directory_the_app_writes_into(self, runtime_dirs):
        """Also the parents a fresh machine has none of: the library folders are
        four levels under a suite root that does not exist yet either.
        """
        ensure_runtime_dirs()

        missing = sorted(name for name, path in runtime_dirs.items() if not path.is_dir())
        assert missing == []

    def test_the_directories_it_creates_are_the_ones_named_here(self):
        """A sixth added to a loop needs a line above, or it escapes."""
        assert _names_ensure_runtime_dirs_creates() == set(_RUNTIME_DIRS)

    def test_a_second_run_keeps_what_the_first_one_left(self, runtime_dirs):
        ensure_runtime_dirs()
        (runtime_dirs["SESSIONS_DIR"] / "demo.json").write_text("{}", encoding="utf-8")

        ensure_runtime_dirs()

        assert (runtime_dirs["SESSIONS_DIR"] / "demo.json").read_text(encoding="utf-8") == "{}"
        assert all(path.is_dir() for path in runtime_dirs.values())


class TestAMachineWithNoLibraryYet:
    """The committed example's ``suite_root`` is a placeholder, not a library.

    ``C:/path/to/suite-root`` is a *relative* path on POSIX, so deriving the
    library folders from it made a literal ``C:`` tree inside the checkout; on
    Windows the same string is absolute and made ``C:\\path\\to\\suite-root`` on
    the system drive. Neither is anywhere clipper should write, and the next
    export would have put real media there -- inside the repo, one ``git add``
    from a public commit.
    """

    def test_a_suite_root_of_its_own_is_what_makes_a_library(
        self, tmp_path: Path, content_overlay
    ):
        content_overlay({"suite_root": str(tmp_path / "library")})

        assert library_is_configured() is True

    def test_a_checkout_with_no_overlay_of_its_own_has_no_library(self, content_overlay):
        """A fresh or public checkout runs on the committed example."""
        content_overlay()

        assert library_is_configured() is False

    def test_an_unedited_copy_of_the_example_is_not_a_library_either(
        self, tmp_path: Path, content_overlay
    ):
        """Setting a machine up is copy-then-edit, and this is between the two.

        Asking whether a ``content.local.json`` exists answers yes here, which
        is how the ``C:`` tree came back while a guard was supposedly stopping it.
        """
        local = content_overlay()
        local.write_text(
            content.EXAMPLE_CONTENT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        content.load_content.cache_clear()

        assert library_is_configured() is False

    def test_the_repos_own_directories_are_still_made(self, checkout_dirs, content_overlay):
        content_overlay()

        ensure_runtime_dirs()

        assert checkout_dirs["SESSIONS_DIR"].is_dir()
        assert checkout_dirs["RAW_CLIPS_DIR"].is_dir()

    def test_no_library_directory_is_made(self, checkout_dirs, content_overlay):
        """What changed, not what is there: the placeholder is an absolute path
        on Windows, so a machine that ran the code this guards against still has
        that tree on its system drive and would answer "is there" yes.
        """
        content_overlay()
        library = (clips_dir(), vr_clips_dir(), audio_dir())
        already = [folder for folder in library if folder.is_dir()]

        ensure_runtime_dirs()

        assert [folder for folder in library if folder.is_dir()] == already


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
