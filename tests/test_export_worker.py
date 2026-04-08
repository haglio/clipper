"""Tests for clipper.gui.export_worker — QThread-based export."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.export_worker import ExportWorker
from clipper.state import ExportJob, VideoState


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_state() -> VideoState:
    import numpy as np

    cap = MagicMock()
    frames = {i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(300)}
    return VideoState(
        cap=cap, path="C:/fake/video.mp4", fps=30.0, total_frames=300,
        loaded_start=0, loaded_end=299, active_start=10, active_end=50,
        current=10, base_step=1, frames=frames, loop_anchor=0.0,
        session_name="test_session", session_path="C:/fake/session.json",
        original_session_payload={},
    )


class TestConstruction:
    def test_has_signals(self):
        worker = ExportWorker.__dict__
        # Verify signals are defined on the class
        assert "stage_changed" in worker
        assert "clip_progress" in worker
        assert "fix_progress" in worker
        assert "audio_progress" in worker
        assert "export_finished" in worker


class TestRunCallsExportSteps:
    """ExportWorker.run() must call export_steps functions with correct signatures."""

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_calls_export_raw_clip_with_path_and_job(
        self, mock_raw, mock_post, mock_audio
    ):
        mock_raw.return_value = (True, "C:/fake/raw.mp4")
        mock_post.return_value = (True, "C:/fake/clip.mp4")
        mock_audio.return_value = (True, "C:/fake/audio.mp3")

        state = _make_state()
        worker = ExportWorker(state)
        worker.run()

        args, kwargs = mock_raw.call_args
        assert args[0] is state
        assert isinstance(args[1], Path), "second arg must be an output Path"
        assert isinstance(args[2], ExportJob), "third arg must be an ExportJob"

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_calls_run_clip_postprocess_with_paths_and_job(
        self, mock_raw, mock_post, mock_audio
    ):
        mock_raw.return_value = (True, "C:/fake/raw.mp4")
        mock_post.return_value = (True, "C:/fake/clip.mp4")
        mock_audio.return_value = (True, "C:/fake/audio.mp3")

        state = _make_state()
        worker = ExportWorker(state)
        worker.run()

        args, kwargs = mock_post.call_args
        assert args[0] is state
        assert isinstance(args[1], Path), "second arg must be raw input Path"
        assert isinstance(args[2], Path), "third arg must be clip output Path"
        assert isinstance(args[3], ExportJob), "fourth arg must be an ExportJob"

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_emits_failure_on_raw_clip_error(
        self, mock_raw, mock_post, mock_audio
    ):
        mock_raw.return_value = (False, "ffmpeg not found on PATH")

        state = _make_state()
        worker = ExportWorker(state)
        results = []
        worker.export_finished.connect(lambda ok, msg: results.append((ok, msg)))
        worker.run()

        assert results == [(False, "ffmpeg not found on PATH")]
        mock_post.assert_not_called()
        mock_audio.assert_not_called()

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_emits_success_on_full_pipeline(
        self, mock_raw, mock_post, mock_audio
    ):
        mock_raw.return_value = (True, "raw.mp4")
        mock_post.return_value = (True, "clip.mp4")
        mock_audio.return_value = (True, "audio.mp3")

        state = _make_state()
        worker = ExportWorker(state)
        results = []
        worker.export_finished.connect(lambda ok, msg: results.append((ok, msg)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is True

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_sets_export_job_on_state(
        self, mock_raw, mock_post, mock_audio
    ):
        mock_raw.return_value = (True, "raw.mp4")
        mock_post.return_value = (True, "clip.mp4")
        mock_audio.return_value = (True, "audio.mp3")

        state = _make_state()
        assert state.export_job is None
        worker = ExportWorker(state)
        worker.run()

        assert state.export_job is not None
        assert isinstance(state.export_job, ExportJob)


class TestVrExportPath:
    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_non_vr_exports_to_clips_dir(self, mock_raw, mock_post, mock_audio):
        from clipper.paths import CLIPS_DIR

        mock_raw.return_value = (True, "raw.mp4")
        mock_post.return_value = (True, "clip.mp4")
        mock_audio.return_value = (True, "audio.mp3")

        state = _make_state()
        state.vr = False
        ExportWorker(state).run()

        clip_path = mock_post.call_args.args[2]
        assert clip_path.parent == CLIPS_DIR

    @patch("clipper.export_steps.export_full_audio_mp3")
    @patch("clipper.export_steps.run_clip_postprocess")
    @patch("clipper.export_steps.export_raw_clip")
    def test_vr_exports_to_vr_clips_dir(self, mock_raw, mock_post, mock_audio):
        from clipper.paths import VR_CLIPS_DIR

        mock_raw.return_value = (True, "raw.mp4")
        mock_post.return_value = (True, "clip.mp4")
        mock_audio.return_value = (True, "audio.mp3")

        state = _make_state()
        state.vr = True
        ExportWorker(state).run()

        clip_path = mock_post.call_args.args[2]
        assert clip_path.parent == VR_CLIPS_DIR
