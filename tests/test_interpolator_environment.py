"""The loop fix needs an interpolator this checkout does not carry, and only
prose said so.

``clip_postprocess_pipeline`` reaches for RIFE on every clip it fixes and, when
there is none, falls back to its geometric seam and says nothing -- so a
checkout that never ran ``tools/fetch_rife.py``, or one whose fetch landed half
the files, writes visibly worse clips and looks fine doing it.

The check used to be four tests gated on the interpolator running, which meant
the merge gate -- which fetches it on purpose -- enforced nothing about a
machine that had not, while the suite stayed permanently four skips short of
zero.  The check now lives in :mod:`clipper.interpolator_environment`, which the
app runs at startup on the machine that actually makes clips -- and what is
tested here is the checker itself, against a stand-in checkout, so it runs
everywhere and skips nowhere.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from clipper import app, interpolator_environment
from clipper.interpolator_environment import complaints, locate


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch):
    """A checkout whose interpolator is wherever a test puts it, and nowhere else."""
    monkeypatch.setattr(interpolator_environment, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(interpolator_environment.shutil, "which", lambda _name: None)
    return tmp_path


def _fetched(root: Path, *, models: tuple[bytes, ...] = (b"weights", b"weights")) -> Path:
    """A checkout ``tools/fetch_rife.py`` has run in, as far as a test wants it to
    have finished: the executable, and whichever model files are given bytes."""
    exe = root / interpolator_environment.VENDORED_EXE
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"MZ")
    model_dir = exe.parent / interpolator_environment.MODEL_DIR_NAME
    model_dir.mkdir(exist_ok=True)
    for name, contents in zip(interpolator_environment.MODEL_FILES, models):
        (model_dir / name).write_bytes(contents)
    return exe


class TestWhatTheCheckerSays:

    def test_a_checkout_that_never_fetched_is_told_how_to(self, checkout: Path):
        (said,) = complaints()

        assert "tools/fetch_rife.py" in said
        assert "geometric seam" in said

    def test_a_fetch_that_landed_no_model_names_what_is_missing(self, checkout: Path):
        """An interrupted extract leaves the executable and not the weights, and
        the binary then starts, fails per frame and falls back the slow way."""
        _fetched(checkout, models=())

        (said,) = complaints()

        assert "flownet.bin" in said
        assert "flownet.param" in said
        assert "tools/fetch_rife.py" in said

    def test_a_weights_file_left_empty_is_not_a_fetch_that_finished(self, checkout: Path):
        _fetched(checkout, models=(b"weights", b""))

        (said,) = complaints()

        assert "flownet.param" in said
        assert "flownet.bin" not in said

    def test_a_finished_fetch_draws_no_complaint(self, checkout: Path):
        """Without this the complaint above could be unconditional and still pass."""
        _fetched(checkout)

        assert complaints() == []


class TestWhichInterpolatorIsUsed:
    """Whether this answers gates the whole RIFE seam path, and its only
    unconditional test used to be ``result is None or isinstance(result, str)``,
    which the return annotation already guarantees -- so a lookup that returned
    a wrong-but-stringy path was indistinguishable from a working one."""

    def test_the_copy_fetched_into_this_checkout_is_the_one_used(self, checkout: Path):
        exe = _fetched(checkout)

        assert locate() == (exe, exe.parent / interpolator_environment.MODEL_DIR_NAME)

    def test_the_fetched_copy_beats_one_installed_on_the_path(
        self, checkout: Path, monkeypatch
    ):
        exe = _fetched(checkout)
        elsewhere = _fetched(checkout / "installed")
        monkeypatch.setattr(
            interpolator_environment.shutil, "which", lambda _name: str(elsewhere))

        assert locate()[0] == exe

    def test_one_installed_on_the_path_is_used_when_this_checkout_has_none(
        self, checkout: Path, monkeypatch
    ):
        elsewhere = _fetched(checkout / "installed")
        monkeypatch.setattr(
            interpolator_environment.shutil, "which", lambda _name: str(elsewhere))

        assert locate()[0] == elsewhere

    def test_a_directory_where_the_executable_should_be_is_not_one(self, checkout: Path):
        (checkout / interpolator_environment.VENDORED_EXE).mkdir(parents=True)

        assert locate() is None

    def test_an_interpolator_with_no_weights_is_not_reached_for_at_all(
        self, checkout: Path
    ):
        """The same question the checker answers on the way up: a binary with
        nothing to interpolate with would start, fail on every frame and fall
        back anyway, one spawned process per frame later."""
        _fetched(checkout, models=())

        assert locate() is None


class _RecordingLog:
    """Clipper's logger, as far as ``main`` uses one."""

    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, message: str, *args) -> None:
        self.warnings.append(message % args)

    def exception(self, message: str) -> None:
        raise AssertionError(f"the launch crashed: {message}")


class TestWhereTheComplaintsGo:
    """A checker nothing calls is the skip it replaced, wearing a module."""

    def test_the_launch_writes_what_the_checker_says_into_clippers_log(self, monkeypatch):
        logged = _RecordingLog()
        monkeypatch.setattr(app, "complaints", lambda: ["no interpolator here"])
        monkeypatch.setattr(app, "_set_windows_app_user_model_id", lambda: None)
        monkeypatch.setattr(app, "_name_this_process", lambda: None)
        monkeypatch.setattr(app, "_init_logger", lambda: logged)
        monkeypatch.setattr(app, "launch_state", lambda: None)

        assert app.main() == 0
        assert logged.warnings == ["Frame interpolator: no interpolator here"]
