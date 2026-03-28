from __future__ import annotations

import importlib
import json
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

def test_create_session_importable_without_cv2():
    """create_session must not transitively import cv2 (or numpy)."""
    sentinel = "cv2"
    real_cv2 = sys.modules.get(sentinel)
    sys.modules[sentinel] = None  # type: ignore[assignment]  # block cv2
    try:
        mod = importlib.import_module("clipper.create_session")
        importlib.reload(mod)
    finally:
        if real_cv2 is not None:
            sys.modules[sentinel] = real_cv2
        else:
            sys.modules.pop(sentinel, None)


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


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

def _mock_ffprobe(fps: float = 30.0, total_frames: int = 900):
    return patch(
        "clipper.create_session._ffprobe_video_metadata",
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


def test_create_session_ffprobe_failure(tmp_path):
    with patch(
        "clipper.create_session._ffprobe_video_metadata",
        side_effect=RuntimeError("ffprobe failed"),
    ):
        with pytest.raises(RuntimeError, match="ffprobe failed"):
            create_session("nonexistent.mp4", 0.0, sessions_dir=tmp_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_success(tmp_path):
    with _mock_ffprobe(), \
         patch("clipper.create_session.SESSIONS_DIR", tmp_path):
        code = main(["--video", r"C:\videos\CliTest.mp4", "--time", "5.0", "--seconds", "3.0"])

    assert code == 0
    assert (tmp_path / "CliTest.json").exists()


def test_cli_failure():
    with patch(
        "clipper.create_session._ffprobe_video_metadata",
        side_effect=RuntimeError("no video"),
    ):
        code = main(["--video", "bad.mp4", "--time", "0"])

    assert code == 1
