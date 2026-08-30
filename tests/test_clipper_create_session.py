from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clipper.create_session import (
    build_session_payload,
    create_session,
    main,
)


# ---------------------------------------------------------------------------
# import isolation — create_session must not pull in cv2
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_create_session_importable_without_cv2():
    """create_session must not transitively import cv2 (or numpy).

    In a fresh interpreter, the way `test_launch_smoke.py` runs its import
    checks. This used to block cv2 by writing None into this process's
    `sys.modules` and reloading the module in place -- and it never undid the
    reload, so every module that had already done
    `from clipper.create_session import create_session` went on holding the
    pre-reload function while the module's own globals were the post-reload
    ones, and a patch applied to one was invisible to the other. Nothing depends
    on that today, which is why it never bit; it was a latent order dependence
    sitting in a session-wide namespace. It also had no assertion, so a reload
    that produced a broken module passed just the same.
    """
    probe = (
        "import sys; sys.modules['cv2'] = None; sys.modules['numpy'] = None; "
        "import clipper.create_session"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    result = subprocess.run([sys.executable, "-c", probe], cwd=REPO_ROOT,
                            env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# build_session_payload
# ---------------------------------------------------------------------------

def test_build_session_payload_basic():
    payload = build_session_payload(
        r"C:\videos\Demo Video.mp4",
        10.0,
        30.0,
        900,
        session_name="Demo",
        seconds=5.0,
    )
    assert payload["version"] == 1
    assert payload["session_name"] == "Demo"
    assert payload["video_path"] == r"C:\videos\Demo Video.mp4"
    assert payload["fps"] == 30.0
    assert payload["total_frames"] == 900
    assert payload["loaded_start"] == 300
    assert payload["loaded_end"] == 449
    assert payload["active_start"] == 300
    assert payload["active_end"] == 449
    assert payload["current"] == 300
    assert payload["seconds_per_step"] == pytest.approx(30.0 / 30.0)
    assert payload["loop_mode"] == "base-tip-base"
    assert payload["wrap_mode"] == "blue"
    assert payload["speed"] == 1.0


def test_build_session_payload_defaults_session_name_from_stem():
    payload = build_session_payload(r"C:\videos\My Cool Video.mp4", 0.0, 24.0, 240)
    assert payload["session_name"] == "My Cool Video"


def test_build_session_payload_clamps_at_video_end():
    payload = build_session_payload("video.mp4", 100.0, 30.0, 100)
    assert payload["loaded_start"] == 99
    assert payload["loaded_end"] == 99
    assert payload["current"] == 99


def test_build_session_payload_clamps_at_video_start():
    payload = build_session_payload("video.mp4", -5.0, 30.0, 900)
    assert payload["loaded_start"] == 0
    assert payload["current"] == 0


def test_build_session_payload_end_clamps_to_total_frames():
    payload = build_session_payload("video.mp4", 0.0, 30.0, 50, seconds=5.0)
    assert payload["loaded_end"] == 49


def test_build_session_payload_vr_defaults_false():
    payload = build_session_payload("video.mp4", 0.0, 30.0, 900)
    assert payload["vr"] is False


def test_build_session_payload_vr_true():
    payload = build_session_payload("video.mp4", 0.0, 30.0, 900, vr=True)
    assert payload["vr"] is True


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

def _mock_ffprobe(fps: float = 30.0, total_frames: int = 900):
    return patch(
        "clipper.create_session.ffprobe_video_metadata",
        return_value=(fps, total_frames),
    )


def test_create_session_writes_json(tmp_path):
    with _mock_ffprobe():
        result = create_session(
            r"C:\videos\TestVideo.mp4",
            10.0,
            sessions_dir=tmp_path,
        )

    assert result == tmp_path / "TestVideo.json"
    assert result.exists()
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["session_name"] == "TestVideo"
    assert payload["video_path"] == r"C:\videos\TestVideo.mp4"
    assert payload["fps"] == 30.0


def test_a_write_that_fails_says_which_file_it_was(tmp_path):
    """The CLI turns this into an `ERROR:` line and a non-zero exit.

    It used to hand-roll the tmp-file-then-replace that `safe_atomic_write_json`
    already does, and re-raise whatever the filesystem raised; now it goes
    through the one writer and names the path, so the caller is told which
    session did not get written.
    """
    with _mock_ffprobe(), patch(
        "clipper.create_session.safe_atomic_write_json",
        return_value=(False, "no space left on device"),
    ):
        with pytest.raises(RuntimeError, match="no space left on device") as failure:
            create_session("D:/media/example/beta rehearsal.mp4", 10.0, sessions_dir=tmp_path)

    assert "beta rehearsal.json" in str(failure.value)


def test_create_session_skips_existing(tmp_path):
    existing = tmp_path / "TestVideo.json"
    existing.write_text('{"existing": true}', encoding="utf-8")

    with _mock_ffprobe():
        result = create_session(
            r"C:\videos\TestVideo.mp4",
            10.0,
            sessions_dir=tmp_path,
        )

    assert result == existing
    assert json.loads(existing.read_text(encoding="utf-8")) == {"existing": True}


def test_create_session_custom_name(tmp_path):
    with _mock_ffprobe():
        result = create_session(
            r"C:\videos\SomeLongFilename_v2.mp4",
            0.0,
            session_name="Short Name",
            sessions_dir=tmp_path,
        )

    assert result == tmp_path / "Short Name.json"
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["session_name"] == "Short Name"


def test_create_session_sanitizes_name(tmp_path):
    with _mock_ffprobe():
        result = create_session(
            r"C:\videos\Bad<>Name.mp4",
            0.0,
            sessions_dir=tmp_path,
        )

    assert result.name == "Bad__Name.json"


def test_create_session_updates_last_session_file(tmp_path):
    last_session = tmp_path / ".last_session.txt"
    with _mock_ffprobe(), \
         patch("clipper.create_session.LAST_SESSION_FILE", last_session):
        result = create_session(
            r"C:\videos\TestVideo.mp4",
            10.0,
            sessions_dir=tmp_path,
        )

    assert last_session.exists()
    assert last_session.read_text(encoding="utf-8") == str(result)


def test_create_session_updates_last_session_even_when_existing(tmp_path):
    existing = tmp_path / "TestVideo.json"
    existing.write_text('{"existing": true}', encoding="utf-8")
    last_session = tmp_path / ".last_session.txt"

    with _mock_ffprobe(), \
         patch("clipper.create_session.LAST_SESSION_FILE", last_session):
        result = create_session(
            r"C:\videos\TestVideo.mp4",
            10.0,
            sessions_dir=tmp_path,
        )

    assert last_session.read_text(encoding="utf-8") == str(result)


def test_create_session_ffprobe_failure(tmp_path):
    with patch(
        "clipper.create_session.ffprobe_video_metadata",
        side_effect=RuntimeError("ffprobe failed"),
    ):
        with pytest.raises(RuntimeError, match="ffprobe failed"):
            create_session("nonexistent.mp4", 0.0, sessions_dir=tmp_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_success(tmp_path, capsys):
    """The CLI is what fun_time invokes; its two outputs are the file and the
    path it prints, and it also moves the pointer the launcher opens next."""
    last_session = tmp_path / ".last_session.txt"

    with _mock_ffprobe(), \
         patch("clipper.create_session.SESSIONS_DIR", tmp_path), \
         patch("clipper.create_session.LAST_SESSION_FILE", last_session):
        code = main(["--video", r"C:\videos\CliTest.mp4", "--time", "5.0", "--seconds", "3.0"])

    assert code == 0
    session = tmp_path / "CliTest.json"
    assert session.exists()
    assert capsys.readouterr().out.strip() == str(session)
    assert last_session.read_text(encoding="utf-8") == str(session)


def test_cli_writes_the_window_it_was_asked_for(tmp_path):
    """A forward-slash path, so this one case reads the same on both platforms."""
    with _mock_ffprobe(), \
         patch("clipper.create_session.SESSIONS_DIR", tmp_path):
        main(["--video", "/library/seaside walk.mp4", "--time", "5.0", "--seconds", "3.0"])

    payload = json.loads((tmp_path / "seaside walk.json").read_text(encoding="utf-8"))
    assert payload["active_start"] == 150  # 5s at 30fps
    assert payload["active_end"] == 239  # plus three seconds, inclusive


def test_cli_failure(capsys):
    with patch(
        "clipper.create_session.ffprobe_video_metadata",
        side_effect=RuntimeError("no video"),
    ):
        code = main(["--video", "bad.mp4", "--time", "0"])

    assert code == 1
    assert "no video" in capsys.readouterr().err
