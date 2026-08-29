"""The fetch step that stands in for 17 MB of binary this repo stopped tracking.

Two things have to hold or the move is worse than the tracking was. The files
must land where ``_find_rife_exe`` looks, or the fetch is green and the suite
skips the RIFE tests anyway; and "the binary is here" has to mean "the binary
runs here", or a machine that fetched the Windows release gets four failures
where it meant to get four skips.
"""
from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from clipper.clip_postprocess_transforms import _find_rife_exe
from tools import fetch_rife

_RELEASE_BYTES = b"pretend release"


def _release_zip(path: Path) -> Path:
    """A stand-in for the upstream asset: the six members, and a model to leave.

    Contents are invented -- the point is which names come out, not what is in
    them.
    """
    with zipfile.ZipFile(path, "w") as zf:
        for member in fetch_rife.MEMBERS:
            zf.writestr(
                f"rife-ncnn-vulkan-{fetch_rife.RELEASE}-windows/{member}",
                f"contents of {member}\n",
            )
        zf.writestr(
            f"rife-ncnn-vulkan-{fetch_rife.RELEASE}-windows/rife-anime/flownet.bin",
            "a model nothing opens\n",
        )
    return path


def _never_called(*_args, **_kwargs):
    raise AssertionError("an intact archive should not be downloaded again")


class TestWhereItLands:
    def test_the_app_finds_what_the_fetch_step_extracts(self, tmp_path: Path):
        """The script's destination and _find_rife_exe's first candidate agree.

        Each spells the path for itself. This is the test that reds if either
        one moves.
        """
        relative = fetch_rife.DEST.relative_to(fetch_rife.TOOLS_DIR.parent)
        exe = tmp_path / relative / fetch_rife.RIFE_EXE.name
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")

        assert _find_rife_exe(str(tmp_path)) == str(exe)


class TestExtract:
    def test_it_writes_every_member_it_names(self, tmp_path: Path):
        dest = tmp_path / "out"

        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), dest)

        written = sorted(
            p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()
        )
        assert written == sorted(fetch_rife.MEMBERS)

    def test_it_leaves_the_models_the_code_never_opens(self, tmp_path: Path):
        """One model directory is asked for by name; the other ten stay in the zip."""
        dest = tmp_path / "out"

        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), dest)

        assert not (dest / "rife-anime").exists()

    def test_the_bytes_are_the_archives(self, tmp_path: Path):
        dest = tmp_path / "out"

        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), dest)

        assert (dest / "rife-v4.6" / "flownet.bin").read_text(encoding="utf-8") == (
            "contents of rife-v4.6/flownet.bin\n"
        )


class TestIsPresent:
    def test_all_six_extracted_is_present(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path)
        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), tmp_path)

        assert fetch_rife.is_present() is True

    def test_one_missing_file_is_not_present(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path)
        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), tmp_path)
        (tmp_path / "vcomp140.dll").unlink()

        assert fetch_rife.is_present() is False


class TestRuns:
    """Presence is not runnability, which is the whole point of the predicate."""

    @pytest.fixture()
    def extracted(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path)
        monkeypatch.setattr(fetch_rife, "RIFE_EXE", tmp_path / "rife-ncnn-vulkan.exe")
        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), tmp_path)
        return tmp_path

    def test_nothing_extracted_does_not_run(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path / "empty")

        assert fetch_rife.runs() is False

    def test_a_file_this_machine_cannot_execute_does_not_run(self, extracted: Path):
        """What every non-Windows machine sees: the file is there and refuses."""
        assert fetch_rife.runs() is False

    def test_a_binary_that_starts_at_all_runs(self, extracted: Path, monkeypatch):
        """Any completed run counts: with no arguments it prints usage and exits."""
        monkeypatch.setattr(
            fetch_rife.subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0], 255, b"", b"usage:"),
        )

        assert fetch_rife.runs() is True

    def test_a_binary_that_never_returns_does_not_run(self, extracted: Path, monkeypatch):
        def _hang(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="rife", timeout=1)

        monkeypatch.setattr(fetch_rife.subprocess, "run", _hang)

        assert fetch_rife.runs() is False


class TestDownload:
    """432 MB for six files, so a re-run must not fetch what it already holds."""

    def test_an_intact_copy_already_there_is_reused(self, tmp_path: Path, monkeypatch):
        archive = tmp_path / fetch_rife.ASSET
        archive.write_bytes(_RELEASE_BYTES)
        monkeypatch.setattr(fetch_rife, "SHA256", hashlib.sha256(_RELEASE_BYTES).hexdigest())
        monkeypatch.setattr(fetch_rife.urllib.request, "urlretrieve", _never_called)

        assert fetch_rife.download(archive) == archive

    def test_a_truncated_copy_is_fetched_again(self, tmp_path: Path, monkeypatch):
        archive = tmp_path / fetch_rife.ASSET
        archive.write_bytes(b"half a download")
        fetched: list[str] = []

        def _fetch(url, target):
            fetched.append(url)
            Path(target).write_bytes(_RELEASE_BYTES)

        monkeypatch.setattr(fetch_rife, "SHA256", hashlib.sha256(_RELEASE_BYTES).hexdigest())
        monkeypatch.setattr(fetch_rife.urllib.request, "urlretrieve", _fetch)

        fetch_rife.download(archive)

        assert fetched == [fetch_rife.URL]

    def test_a_download_that_does_not_match_is_refused_and_removed(
        self, tmp_path: Path, monkeypatch
    ):
        archive = tmp_path / fetch_rife.ASSET

        def _fetch(_url, target):
            Path(target).write_bytes(b"something else entirely")

        monkeypatch.setattr(fetch_rife.urllib.request, "urlretrieve", _fetch)

        with pytest.raises(SystemExit, match="sha256 mismatch"):
            fetch_rife.download(archive)

        assert not archive.exists()
