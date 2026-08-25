"""Shared pytest fixtures for clipper tests."""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pytest

# Render Qt offscreen for the whole suite. Agents run these tests on every commit
# on the machine clipper is used from; without this, every test that builds a
# widget throws a real window onto that screen for a few milliseconds, so a run
# flashes a burst of them. Must be set before the QApplication below exists, so
# it goes here rather than in a fixture; the merge gate sets it too, which does
# nothing for a run started by hand. setdefault lets a developer override it to
# watch something on a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402  -- after the platform is set


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """The one QApplication the Qt tests build their widgets under.

    Twelve test modules used to carry a byte-identical copy of this, beside a
    `tests/conftest_qt.py` that looked like the shared version and was never
    loaded -- pytest only auto-loads files named `conftest.py`, and nothing
    imported it. So the shared one was dead and the change it exists to make
    possible had to be made twelve times.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ---------------------------------------------------------------------------
# sys.path fix — must run before clipper is imported
# ---------------------------------------------------------------------------
# pytest inserts ancestor directories of the test root into sys.path.  When
# the monorepo "projects" directory ends up there, Python resolves "clipper"
# as the *project root* directory (a namespace package) instead of the real
# clipper package installed via editable pip.  That causes clipper.state to
# resolve to the runtime ``state/`` log directory rather than state.py,
# breaking every import of VideoState / ExportJob.
#
# Fix: force-import clipper from the editable-install finder before pytest
# collection triggers a namespace-package resolution.  Once the correct
# module is in sys.modules the bad path can't win.
import importlib as _importlib

_spec = _importlib.util.find_spec("clipper")
if _spec is None or _spec.origin is None:
    # The editable finder lost the race.  Flush the stale entry and retry
    # by looking up the installed package location directly.
    sys.modules.pop("clipper", None)
    _importlib.invalidate_caches()

    # Import the editable-install's finder and ask it directly.
    import __editable___clipper_0_1_0_finder as _finder  # type: ignore[import-untyped]
    _pkg_path = _finder.MAPPING.get("clipper")
    if _pkg_path:
        _init = Path(_pkg_path) / "__init__.py"
        if _init.is_file():
            _new_spec = _importlib.util.spec_from_file_location(
                "clipper", str(_init),
                submodule_search_locations=[_pkg_path],
            )
            if _new_spec and _new_spec.loader:
                _mod = _importlib.util.module_from_spec(_new_spec)
                sys.modules["clipper"] = _mod
                _new_spec.loader.exec_module(_mod)


def pytest_collection_modifyitems(items):
    """Collect in a different order when asked, so a test that leans on the ones
    beside it fails on the commit that introduces the lean.

    ``TEST_COLLECTION_ORDER=reverse`` collects back to front;
    ``TEST_COLLECTION_ORDER=shuffle`` shuffles with ``TEST_COLLECTION_SEED`` (0
    unless given), so a red run can be repeated exactly.  Unset leaves the order
    alone; anything else is a typo, and a typo that silently ran forward would
    make the gate's second leg a green that proves nothing.
    """
    order = os.environ.get("TEST_COLLECTION_ORDER")
    if order is None:
        return
    if order == "reverse":
        items.reverse()
    elif order == "shuffle":
        random.Random(int(os.environ.get("TEST_COLLECTION_SEED", "0"))).shuffle(items)
    else:
        raise pytest.UsageError(
            f"TEST_COLLECTION_ORDER={order!r}: expected 'reverse' or 'shuffle'"
        )


TMP_ROOT = Path(
    os.environ.get(
        "FUN_TIME_PYTEST_TMP_ROOT",
        str(Path(__file__).resolve().parent.parent / ".tmp-pytest-local"),
    )
).resolve()


@pytest.fixture()
def tmp_path() -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = (TMP_ROOT / f"case_{uuid.uuid4().hex}").resolve()
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def _cleanup_tmp_root():
    """Remove TMP_ROOT after the session if it exists and is empty."""
    yield
    try:
        if TMP_ROOT.is_dir() and not any(TMP_ROOT.iterdir()):
            TMP_ROOT.rmdir()
    except OSError:
        pass


@pytest.fixture(autouse=True, scope="session")
def _the_last_session_pointer_is_never_the_real_one():
    """Point every module that binds LAST_SESSION_FILE at a scratch file.

    Five tests reached the user's own `.last_session.txt` by omission: they call
    `create_session` with a `sessions_dir`, and nothing patches the pointer it
    *also* writes. This used to be met by saving the file before the run and
    writing it back afterwards -- which never happened when a run was
    interrupted, timed out or killed, routine on a machine where several agents
    run suites at once, and which raced itself when two ran in the same
    checkout. Redirecting the name instead means a test cannot reach the real
    file by forgetting; the tests that assert on the pointer patch their own.
    """
    import importlib

    scratch = TMP_ROOT / ".last_session.txt"
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as patcher:
        for name in ("clipper.paths", "clipper.create_session",
                     "clipper.session_launch", "clipper.session_persistence"):
            patcher.setattr(importlib.import_module(name),
                            "LAST_SESSION_FILE", scratch)
        yield
    scratch.unlink(missing_ok=True)


class _FakeCapture:
    """The slice of cv2.VideoCapture that frame_store.load_range actually uses.

    A MagicMock cannot stand in for it: `ok, frame = cap.read()` unpacks, so a
    test that lets a real ensure_loaded run needs a capture that answers.
    """

    def __init__(self, total_frames: int):
        self._total = total_frames
        self._pos = 0

    def set(self, prop, value) -> bool:
        self._pos = int(value)
        return True

    def read(self):
        if self._pos >= self._total:
            return False, None
        self._pos += 1
        return True, np.zeros((2, 2, 3), dtype=np.uint8)

    def release(self) -> None:
        pass


class _FakeAutosave:
    """Stands in for the session write ``VideoState.mark_dirty`` triggers.

    Counting the calls is what ``patch.object(s, "mark_dirty")`` used to be
    reached for, minus the part that hid the dirty flag itself.
    """

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, state) -> None:
        self.calls += 1


@pytest.fixture()
def rendered():
    """Paint a widget into an image, so a test can read the pixels it drew.

    Nothing in this suite used to assert a painted pixel, so gutting any
    ``paintEvent`` was caught only by the dead-code guard noticing the locals
    it left unused.
    """
    def paint(widget):
        return widget.grab().toImage()
    return paint


@pytest.fixture()
def frames_of():
    """One solid BGR frame per value -- the shape the loop transforms read in.

    1x1 by default, which is enough for the pure transforms; ``size`` gives the
    pipeline cases frames big enough for the shrink loop to have somewhere to go.
    """
    def factory(values: list[int], size: int = 1) -> list[np.ndarray]:
        return [np.full((size, size, 3), value, dtype=np.uint8) for value in values]
    return factory


@pytest.fixture()
def values_of():
    """The inverse of ``frames_of``: read each frame back as its one value."""
    def factory(frames: list[np.ndarray]) -> list[int]:
        return [int(frame[0, 0, 0]) for frame in frames]
    return factory


@pytest.fixture()
def make_state():
    """Factory for a VideoState the tests can edit without a disk or a codec.

    Two modules held their own version of this and two more imported one of
    them across module boundaries -- which worked only because tests/ has no
    __init__.py and pytest prepends the directory to sys.path, so renaming
    test_clipper_state.py broke two unrelated files.
    """
    from clipper.state import VideoState

    def factory(
        *,
        total_frames: int = 100,
        loaded_start: int = 0,
        loaded_end: int | None = None,
        active_start: int = 10,
        active_end: int | None = None,
        current: int = 20,
        base_step: int = 5,
        fps: float = 30.0,
        speed: float = 1.0,
        wrap_mode: str = "blue",
        loop_mode: str = "base-tip-base",
        session_name: str = "test_session",
        path: str = "/fake/video.mp4",
        session_path: str = "/fake/sessions/test_session.json",
        initial_active_start: int | None = None,
        initial_active_end: int | None = None,
    ) -> VideoState:
        if loaded_end is None:
            loaded_end = total_frames - 1
        if active_end is None:
            active_end = total_frames - 10
        return VideoState(
            cap=_FakeCapture(total_frames),
            path=path,
            fps=fps,
            total_frames=total_frames,
            loaded_start=loaded_start,
            loaded_end=loaded_end,
            active_start=active_start,
            active_end=active_end,
            current=current,
            base_step=base_step,
            frames={
                i: np.zeros((2, 2, 3), dtype=np.uint8)
                for i in range(loaded_start, loaded_end + 1)
            },
            loop_anchor=time.monotonic(),
            session_name=session_name,
            session_path=session_path,
            original_session_payload={},
            loop_mode=loop_mode,
            speed=speed,
            wrap_mode=wrap_mode,
            initial_active_start=(
                active_start if initial_active_start is None else initial_active_start
            ),
            initial_active_end=(
                active_end if initial_active_end is None else initial_active_end
            ),
            persist_session=_FakeAutosave(),
        )

    return factory


def _write_config(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a minimal valid config JSON to tmp_path and return the path."""
    # Create stub directories / files that config validation expects.
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "clips").mkdir(exist_ok=True)
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "portrait").mkdir(exist_ok=True)
    (tmp_path / "landscape").mkdir(exist_ok=True)
    (tmp_path / "weird").mkdir(exist_ok=True)
    (tmp_path / "vlc_primary").mkdir(exist_ok=True)

    cfg: dict = {
        "paths": {
            "vlc_exe": str(tmp_path / "vlc.exe"),
            "mfp_exe": str(tmp_path / "mfp.exe"),
            "ahk_exe": str(tmp_path / "ahk.exe"),
            "python_exe": str(tmp_path / "python.exe"),
            "primary_vlc_dirs": [str(tmp_path / "vlc_primary")],
            "portrait_dir": str(tmp_path / "portrait"),
            "landscape_dir": str(tmp_path / "landscape"),
            "weird_dir": str(tmp_path / "weird"),
            "clips_dir": str(tmp_path / "clips"),
            "audio_dir": str(tmp_path / "audio"),
            "favs_file": str(tmp_path / "favs.csv"),
            "state_dir": str(tmp_path / "state"),
        },
        "controller": {
            "primary_vlc_http_port": 8090,
            "vlc2_http_port": 8091,
            "vlc3_http_port": 8092,
            "layout": {
                "main_monitor": 1,
                "secondary_monitor": 2,
                "primary_top_ratio": 0.727,
                "landscape_width_ratio": 0.666,
                "mfp_width_ratio": 0.9,
                "mfp_height_ratio": 0.6,
            },
        },
        "broker": {
            "virtual_port": "COM15",
            "real_port": "COM4",
            "baud": 115200,
            "udp_host": "127.0.0.1",
            "udp_port": 50555,
            "auto_stale_timeout": 8.0,
        },
        "genau": {
            "shuffle_on_load": True,
            "beats_per_loop": 1.0,
            "clip_cache_size": 2,
            "render_batch": 6,
            "bpm_smoothing": 0.14,
            "sync_strength": 0.35,
            "udp_host": "127.0.0.1",
            "udp_port": 50555,
            "notify_host": "127.0.0.1",
            "notify_port": 50556,
            "status_hide_ms": 1200,
            "resize_debounce_ms": 120,
        },
        "audio_companion": {
            "host": "127.0.0.1",
            "port": 50556,
        },
    }

    if overrides:
        _deep_merge(cfg, overrides)

    config_path = tmp_path / "fun_time_config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    return config_path


def _deep_merge(base: dict, override: dict) -> None:
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


@pytest.fixture()
def cfg_path(tmp_path: Path) -> Path:
    """Return path to a written minimal valid config file."""
    return _write_config(tmp_path)


@pytest.fixture()
def cfg_factory(tmp_path: Path):
    """Return a factory that writes a config with optional overrides."""
    def factory(overrides: dict | None = None) -> Path:
        return _write_config(tmp_path, overrides)
    return factory
