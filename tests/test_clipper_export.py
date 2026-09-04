"""Tests for clipper.export (pure-logic and lightly-mocked)."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from clipper.export_steps import (
    _parse_ffmpeg_clock,
    _run_ffmpeg_with_progress,
    export_full_audio_mp3,
    run_clip_postprocess,
    validate_video_file,
)


class _Recorder:
    """Stands in for whoever is watching the export."""

    def __init__(self) -> None:
        self.stages: list[str] = []
        self.clips: list[float] = []
        self.fixes: list[float] = []
        self.audios: list[float] = []

    def stage(self, text: str) -> None:
        self.stages.append(text)

    def clip(self, fraction: float) -> None:
        self.clips.append(fraction)

    def fix(self, fraction: float) -> None:
        self.fixes.append(fraction)

    def audio(self, fraction: float) -> None:
        self.audios.append(fraction)


# ---------------------------------------------------------------------------
# _parse_ffmpeg_clock
# ---------------------------------------------------------------------------

# What ffmpeg prints on its progress line, and the seconds it means. The eight
# one-line methods this replaces differed only in these two values.
_FFMPEG_CLOCKS = [
    ("00:00:00.000000", 0.0),
    ("00:00:30.000000", 30.0),
    ("00:01:00.000000", 60.0),
    ("01:00:00.000000", 3600.0),
    ("01:02:03.500000", 3723.5),
    ("00:00:30", 30.0),
]


class TestParseFfmpegClock:
    @pytest.mark.parametrize("printed, seconds", _FFMPEG_CLOCKS)
    def test_it_reads_the_clock_ffmpeg_prints(self, printed, seconds):
        assert _parse_ffmpeg_clock(printed) == pytest.approx(seconds)

    @pytest.mark.parametrize("printed", ["N/A", "", "not:a:number", "00:00"])
    def test_anything_it_cannot_read_counts_as_no_progress(self, printed):
        """A progress line it cannot parse must not move the bar backwards."""
        assert _parse_ffmpeg_clock(printed) == 0.0


# ---------------------------------------------------------------------------
# validate_video_file
# ---------------------------------------------------------------------------

class TestValidateVideoFile:
    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        ok, msg = validate_video_file(tmp_path / "ghost.mp4")
        assert ok is False
        assert "not created" in msg.lower() or "exist" in msg.lower()

    def test_tiny_file_returns_false(self, tmp_path: Path):
        tiny = tmp_path / "tiny.mp4"
        tiny.write_bytes(b"\x00" * 100)  # less than 2048 bytes
        ok, msg = validate_video_file(tiny)
        assert ok is False
        assert "tiny" in msg.lower()

    def test_unreadable_cv2_file_returns_false(self, tmp_path: Path):
        fake = tmp_path / "fake.mp4"
        fake.write_bytes(b"\x00" * 4096)  # big enough bytes-wise but invalid video

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap.read.return_value = (False, None)

        with patch("clipper.export_steps.cv2.VideoCapture", return_value=mock_cap):
            ok, msg = validate_video_file(fake)

        assert ok is False
        assert "unreadable" in msg.lower() or "locked" in msg.lower()

    def test_no_readable_frames_returns_false(self, tmp_path: Path):
        fake = tmp_path / "fake.mp4"
        fake.write_bytes(b"\x00" * 4096)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)

        with patch("clipper.export_steps.cv2.VideoCapture", return_value=mock_cap):
            ok, msg = validate_video_file(fake)

        assert ok is False
        assert "no readable frames" in msg.lower()

    def test_valid_file_returns_true(self, tmp_path: Path):
        fake = tmp_path / "ok.mp4"
        fake.write_bytes(b"\x00" * 4096)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        with patch("clipper.export_steps.cv2.VideoCapture", return_value=mock_cap):
            ok, msg = validate_video_file(fake)

        assert ok is True
        assert msg == ""

    def test_cap_released_on_success(self, tmp_path: Path):
        fake = tmp_path / "ok.mp4"
        fake.write_bytes(b"\x00" * 4096)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((2, 2, 3), dtype=np.uint8))

        with patch("clipper.export_steps.cv2.VideoCapture", return_value=mock_cap):
            validate_video_file(fake)

        mock_cap.release.assert_called_once()

    def test_cap_released_on_failure(self, tmp_path: Path):
        fake = tmp_path / "ok.mp4"
        fake.write_bytes(b"\x00" * 4096)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        with patch("clipper.export_steps.cv2.VideoCapture", return_value=mock_cap):
            validate_video_file(fake)

        mock_cap.release.assert_called_once()


# ---------------------------------------------------------------------------
# _run_ffmpeg_with_progress  (mocked subprocess)
# ---------------------------------------------------------------------------

class TestRunFfmpegWithProgress:
    def _make_proc_mock(self, output_lines: list[str], returncode: int = 0) -> MagicMock:
        proc = MagicMock()
        proc.stdout = io.StringIO("\n".join(output_lines))
        proc.wait.return_value = returncode
        proc.poll.return_value = returncode
        return proc

    def test_success_calls_set_progress_to_1(self):
        proc = self._make_proc_mock(["progress=end"])
        progress_values: list[float] = []

        with patch("subprocess.Popen", return_value=proc):
            ok, err = _run_ffmpeg_with_progress(
                ["ffmpeg", "-version"], 10.0, progress_values.append
            )

        assert (ok, err) == (True, "")
        assert progress_values[-1] == pytest.approx(1.0)

    def test_nonzero_exit_returns_false(self):
        proc = self._make_proc_mock([], returncode=1)
        progress_values: list[float] = []

        with patch("subprocess.Popen", return_value=proc):
            ok, err = _run_ffmpeg_with_progress(
                ["ffmpeg", "-version"], 10.0, progress_values.append
            )

        assert ok is False
        assert "1" in err

    def test_launch_failure_returns_false(self):
        with patch("subprocess.Popen", side_effect=FileNotFoundError("not found")):
            ok, err = _run_ffmpeg_with_progress(
                ["ffmpeg"], 10.0, lambda p: None
            )
        assert ok is False
        assert "not found" in err

    def test_out_time_line_advances_progress(self):
        # 5 seconds out of 10 total → 0.5
        proc = self._make_proc_mock(["out_time=00:00:05.000000", "progress=end"])
        recorded: list[float] = []

        with patch("subprocess.Popen", return_value=proc):
            _run_ffmpeg_with_progress(["ffmpeg"], 10.0, recorded.append)

        # At some point 0.5 should have been reported
        assert any(abs(v - 0.5) < 0.01 for v in recorded)

    def test_nonzero_exit_includes_error_output(self):
        proc = self._make_proc_mock(
            ["Stream mapping:", "  No audio stream found", "out_time=00:00:00.000000"],
            returncode=1,
        )
        with patch("subprocess.Popen", return_value=proc):
            ok, err = _run_ffmpeg_with_progress(
                ["ffmpeg", "-version"], 10.0, lambda p: None
            )
        assert ok is False
        assert "No audio stream found" in err

    def test_progress_never_exceeds_1(self):
        # Simulate an out_time that exceeds total duration
        proc = self._make_proc_mock(["out_time=99:00:00.000000", "progress=end"])
        recorded: list[float] = []

        with patch("subprocess.Popen", return_value=proc):
            _run_ffmpeg_with_progress(["ffmpeg"], 1.0, recorded.append)

        assert all(v <= 1.0 for v in recorded)


class TestRunClipPostprocess:
    def test_passes_loop_mode_to_script(self, tmp_path: Path, make_state):
        progress = _Recorder()
        state = make_state(loop_mode="tip-base")
        raw_path = tmp_path / "raw.mp4"
        out_path = tmp_path / "out.mp4"

        proc = MagicMock()
        proc.stdout = io.StringIO("done\n")
        proc.poll.side_effect = [0]
        proc.wait.return_value = 0

        with patch("clipper.export_steps.CLIP_POSTPROCESS_SCRIPT", tmp_path / "clip_postprocess.py"):
            (tmp_path / "clip_postprocess.py").write_text("# test\n", encoding="utf-8")
            with patch("subprocess.Popen", return_value=proc) as popen:
                ok, detail = run_clip_postprocess(state, raw_path, out_path, progress)

        assert ok is True
        assert detail == str(out_path)
        cmd = popen.call_args.args[0]
        assert "--loop-mode" in cmd
        assert "tip-base" in cmd


class TestExportFullAudioMp3:
    def test_skips_when_no_audio_stream(self, tmp_path: Path, make_state):
        """Videos without audio should not fail the entire export."""
        progress = _Recorder()
        state = make_state()
        out_path = tmp_path / "out.mp3"

        # ffprobe reports no audio streams
        probe_proc = MagicMock()
        probe_proc.communicate.return_value = ("", "")
        probe_proc.returncode = 0

        with patch("clipper.export_steps.find_tool", return_value="ffprobe"), \
             patch("subprocess.Popen", return_value=probe_proc):
            ok, detail = export_full_audio_mp3(state, out_path, progress)

        assert ok is True
        assert "no audio" in detail.lower()

    def test_proceeds_when_audio_stream_exists(self, tmp_path: Path, make_state):
        """Normal videos with audio should go through the ffmpeg path."""
        progress = _Recorder()
        state = make_state()
        out_path = tmp_path / "out.mp3"

        # ffprobe reports an audio stream
        probe_proc = MagicMock()
        probe_proc.communicate.return_value = ("audio\n", "")
        probe_proc.returncode = 0

        # ffmpeg succeeds and creates a file
        ffmpeg_proc = MagicMock()
        ffmpeg_proc.stdout = io.StringIO("progress=end\n")
        ffmpeg_proc.wait.return_value = 0
        ffmpeg_proc.poll.return_value = 0

        def popen_side_effect(cmd, **kw):
            if "ffprobe" in cmd[0]:
                return probe_proc
            return ffmpeg_proc

        out_path.write_bytes(b"\xff" * 4096)  # pre-create so size check passes

        with patch("clipper.export_steps.find_tool", side_effect=lambda n: n), \
             patch("subprocess.Popen", side_effect=popen_side_effect):
            ok, detail = export_full_audio_mp3(state, out_path, progress)

        assert ok is True
        assert str(out_path) in detail
