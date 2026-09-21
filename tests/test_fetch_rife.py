"""The fetch step that stands in for 17 MB of binary this repo stopped tracking.

Two things have to hold or the move is worse than the tracking was. The files
must land where ``clipper.interpolator_environment`` looks, or the fetch is
green and the loop fix falls back to its geometric seam anyway; and "the binary
is here" has to mean "the binary runs here", or ``--require`` passes on a
machine that cannot interpolate -- and that one step is the only place anything
asks the real binary for a frame.
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from clipper import interpolator_environment
from tools import fetch_rife

_RELEASE_BYTES = b"pretend release"


def _release_zip(path: Path) -> Path:
    """A stand-in for the upstream asset: the six files, and a model to leave.

    Contents are invented -- the point is which names come out, not what is in
    them.
    """
    with zipfile.ZipFile(path, "w") as zf:
        for name in fetch_rife.FILES:
            zf.writestr(
                f"rife-ncnn-vulkan-{fetch_rife.RELEASE}-windows/{name}",
                f"contents of {name}\n",
            )
        zf.writestr(
            f"rife-ncnn-vulkan-{fetch_rife.RELEASE}-windows/rife-anime/flownet.bin",
            "a model nothing opens\n",
        )
    return path


def _never_called(*_args, **_kwargs):
    raise AssertionError("nothing here should have gone to the network")


class TestWhereItLands:
    """Each of these spells a path for itself, and the app falls back forever
    and silently if the two ever stop agreeing. These are the tests that red."""

    def test_the_app_looks_where_the_fetch_step_extracts(self):
        assert (fetch_rife.RIFE_EXE.relative_to(fetch_rife.TOOLS_DIR.parent)
                == interpolator_environment.VENDORED_EXE)

    def test_the_fetch_step_brings_the_weights_the_app_asks_for(self):
        """The model directory is named twice over -- once in the list of files
        to extract, once in the app's lookup -- and a release that renamed it
        would leave a fetch that reported success and an app that never
        interpolated again."""
        wanted = {f"{interpolator_environment.MODEL_DIR_NAME}/{name}"
                  for name in interpolator_environment.MODEL_FILES}

        assert wanted <= set(fetch_rife.FILES)


class TestExtract:
    def test_it_writes_every_file_it_names(self, tmp_path: Path):
        dest = tmp_path / "out"

        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), dest)

        written = sorted(
            p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()
        )
        assert written == sorted(fetch_rife.FILES)

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


def _bridge_returning(result):
    def _bridge(_a, _b, _n):
        if isinstance(result, Exception):
            raise result
        return result
    return _bridge


class TestRuns:
    """Presence is not runnability, and starting is not interpolating.

    A spawn probe answers yes on a Windows machine with no Vulkan device -- upstream
    prints its usage and exits before touching Vulkan when called with no
    arguments -- so the four seam-bridge tests would run and fail there instead
    of the gate saying why. The predicate asks for a frame.
    """

    @pytest.fixture
    def extracted(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path)
        monkeypatch.setattr(fetch_rife, "RIFE_EXE", tmp_path / "rife-ncnn-vulkan.exe")
        # runs() interpolates through clip_postprocess_transforms, which resolves
        # the binary with interpolator_environment -- not fetch_rife.RIFE_EXE.
        # Point that seam at the extracted fake too, or the Windows runner finds
        # the real fetched exe, produces a frame, and runs() answers True where
        # the whole point is that a present-but-unrunnable file answers False.
        monkeypatch.setattr(
            "clipper.interpolator_environment._find_exe",
            lambda: fetch_rife.RIFE_EXE,
        )
        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), tmp_path)
        return tmp_path

    def test_nothing_extracted_does_not_run(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path / "empty")

        assert fetch_rife.runs() is False

    def test_a_file_this_machine_cannot_execute_does_not_run(self, extracted: Path):
        """What every non-Windows machine sees: the file is there and refuses."""
        assert fetch_rife.runs() is False

    def test_a_bridge_frame_coming_back_is_what_running_means(
        self, extracted: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "clipper.clip_postprocess_transforms.build_rife_bridge",
            _bridge_returning([object()]),
        )

        assert fetch_rife.runs() is True

    def test_a_binary_that_starts_and_interpolates_nothing_does_not_run(
        self, extracted: Path, monkeypatch
    ):
        """The Vulkan-less case: the process runs, the bridge comes back empty."""
        monkeypatch.setattr(
            "clipper.clip_postprocess_transforms.build_rife_bridge",
            _bridge_returning(None),
        )

        assert fetch_rife.runs() is False

    def test_a_bridge_that_raises_does_not_run(self, extracted: Path, monkeypatch):
        monkeypatch.setattr(
            "clipper.clip_postprocess_transforms.build_rife_bridge",
            _bridge_returning(subprocess.TimeoutExpired(cmd="rife", timeout=1)),
        )

        assert fetch_rife.runs() is False


class TestMain:
    """The entry point the merge gate runs, and the flag it runs it with."""

    @pytest.fixture
    def fetched(self, tmp_path: Path, monkeypatch) -> Path:
        """A checkout that already has the files, so main() does not download."""
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path)
        fetch_rife.extract(_release_zip(tmp_path / "release.zip"), tmp_path)
        return tmp_path

    def _with_runs(self, monkeypatch, answer: bool) -> None:
        monkeypatch.setattr(fetch_rife, "runs", lambda: answer)

    def test_it_reports_success_when_the_interpolator_works(self, fetched, monkeypatch):
        self._with_runs(monkeypatch, True)

        assert fetch_rife.main([]) == 0
        assert fetch_rife.main(["--require"]) == 0

    def test_a_binary_that_does_not_run_is_fine_without_require(self, fetched, monkeypatch):
        """A developer machine fetches the Windows release and cannot use it."""
        self._with_runs(monkeypatch, False)

        assert fetch_rife.main([]) == 0

    def test_a_binary_that_does_not_run_fails_under_require(self, fetched, monkeypatch):
        """This is the merge gate's whole assertion."""
        self._with_runs(monkeypatch, False)

        assert fetch_rife.main(["--require"]) == 1

    def test_a_fetch_that_lands_nothing_fails_either_way(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(fetch_rife, "DEST", tmp_path / "nothing")
        monkeypatch.setattr(fetch_rife, "download", lambda *a, **k: tmp_path / "absent.zip")
        monkeypatch.setattr(fetch_rife, "extract", lambda *a, **k: None)

        assert fetch_rife.main([]) == 1
        assert fetch_rife.main(["--require"]) == 1

    def test_it_fetches_only_when_something_is_missing(self, fetched, monkeypatch):
        self._with_runs(monkeypatch, True)
        monkeypatch.setattr(fetch_rife, "download", _never_called)

        assert fetch_rife.main([]) == 0


class TestDownload:
    """432 MB for six files, so a re-run must not fetch what it already holds."""

    def test_an_intact_copy_already_there_is_reused(self, tmp_path: Path, monkeypatch):
        archive = tmp_path / fetch_rife.ASSET
        archive.write_bytes(_RELEASE_BYTES)
        monkeypatch.setattr(fetch_rife, "SHA256", hashlib.sha256(_RELEASE_BYTES).hexdigest())
        monkeypatch.setattr(fetch_rife.urllib.request, "urlopen", _never_called)

        assert fetch_rife.download(archive) == archive

    def test_a_truncated_copy_is_fetched_again(self, tmp_path: Path, monkeypatch):
        archive = tmp_path / fetch_rife.ASSET
        archive.write_bytes(b"half a download")
        fetched: list[str] = []

        def _open(url, timeout=None):
            fetched.append((url, timeout))
            return io.BytesIO(_RELEASE_BYTES)

        monkeypatch.setattr(fetch_rife, "SHA256", hashlib.sha256(_RELEASE_BYTES).hexdigest())
        monkeypatch.setattr(fetch_rife.urllib.request, "urlopen", _open)

        fetch_rife.download(archive)

        assert fetched == [(fetch_rife.URL, fetch_rife._DOWNLOAD_TIMEOUT)]

    def test_a_download_that_does_not_match_is_refused_and_removed(
        self, tmp_path: Path, monkeypatch
    ):
        archive = tmp_path / fetch_rife.ASSET

        def _open(_url, timeout=None):
            return io.BytesIO(b"something else entirely")

        monkeypatch.setattr(fetch_rife.urllib.request, "urlopen", _open)

        with pytest.raises(SystemExit, match="sha256 mismatch"):
            fetch_rife.download(archive)

        assert not archive.exists()
