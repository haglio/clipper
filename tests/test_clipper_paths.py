"""Tests for clipper.paths."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from clipper.paths import (
    AUDIO_DIR,
    CLIPS_DIR,
    RAW_CLIPS_DIR,
    SESSIONS_DIR,
    ensure_runtime_dirs,
)


# ---------------------------------------------------------------------------
# ensure_runtime_dirs
# ---------------------------------------------------------------------------

class TestEnsureRuntimeDirs:
    def test_creates_sessions_dir(self, tmp_path: Path):
        sessions = tmp_path / "sessions"
        clips = tmp_path / "clips"
        raw = tmp_path / "raw_clips"
        audio = tmp_path / "audio"

        with (
            patch("clipper.paths.SESSIONS_DIR", sessions),
            patch("clipper.paths.RAW_CLIPS_DIR", raw),
            patch("clipper.paths.CLIPS_DIR", clips),
            patch("clipper.paths.AUDIO_DIR", audio),
        ):
            ensure_runtime_dirs()

        assert sessions.is_dir()
        assert clips.is_dir()
        assert raw.is_dir()
        assert audio.is_dir()

    def test_idempotent(self, tmp_path: Path):
        sessions = tmp_path / "sessions"
        clips = tmp_path / "clips"
        raw = tmp_path / "raw_clips"
        audio = tmp_path / "audio"

        with (
            patch("clipper.paths.SESSIONS_DIR", sessions),
            patch("clipper.paths.RAW_CLIPS_DIR", raw),
            patch("clipper.paths.CLIPS_DIR", clips),
            patch("clipper.paths.AUDIO_DIR", audio),
        ):
            ensure_runtime_dirs()
            ensure_runtime_dirs()  # Should not raise
