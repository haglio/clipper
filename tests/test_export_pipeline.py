"""The three steps an export runs, driven without a thread or a window.

These cases used to run through ``ExportWorker.run``, which held the whole
sequence inside a QThread -- so the order of the steps, where each output goes
and what happens when one fails could only be asked with Qt in the room.  The
worker's own tests stay where they are: what it does now is call this and turn
the answer into a signal.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from clipper.export_pipeline import run_export
from clipper.paths import RAW_CLIPS_DIR, audio_dir, clips_dir, vr_clips_dir
from clipper.sidecar import record_provenance

pytestmark = pytest.mark.usefixtures("library")


class _Watcher:
    """Whoever is watching the export -- here, a list of what it was told."""

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


class _Step:
    """A stand-in for an export step: records its call, reports progress the
    way the real step does, and answers with whatever it is told to.
    """

    def __init__(self, *, stage: str, reports: str, ok: bool = True, detail: str = ""):
        self.stage_text = stage
        self.reports = reports
        self.ok = ok
        self.detail = detail
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)
        progress = args[-1]
        progress.stage(self.stage_text)
        getattr(progress, self.reports)(1.0)
        return self.ok, self.detail

    @property
    def called(self) -> bool:
        return bool(self.calls)


@pytest.fixture
def state(make_state):
    return make_state(
        path="C:/fake/video.mp4", session_path="C:/fake/session.json",
        total_frames=300, loaded_end=299, active_start=10, active_end=50,
        current=10, base_step=1,
    )


@pytest.fixture
def steps():
    """The three export steps, stubbed at the module they are called through."""
    stubs = {
        "raw": _Step(stage="clipping", reports="clip", detail="raw.mp4"),
        "post": _Step(stage="fixing the loop", reports="fix", detail="clip.mp4"),
        "audio": _Step(stage="pulling audio", reports="audio", detail="audio.mp3"),
    }
    with patch("clipper.export_steps.export_raw_clip", stubs["raw"]), \
         patch("clipper.export_steps.run_clip_postprocess", stubs["post"]), \
         patch("clipper.export_steps.export_full_audio_mp3", stubs["audio"]):
        yield stubs


@pytest.fixture
def watcher():
    return _Watcher()


class TestWhatEachStepIsGiven:
    def test_the_raw_clip_step_gets_the_state_an_output_path_and_the_watcher(
        self, state, steps, watcher
    ):
        run_export(state, watcher)

        clip_state, out_path, progress = steps["raw"].calls[0]
        assert clip_state is state
        assert out_path.parent == RAW_CLIPS_DIR
        assert progress is watcher

    def test_the_post_process_step_gets_the_raw_input_and_the_clip_output(
        self, state, steps, watcher
    ):
        run_export(state, watcher)

        post_state, raw_in, clip_out, progress = steps["post"].calls[0]
        assert post_state is state
        assert raw_in == steps["raw"].calls[0][1]
        assert clip_out.parent == clips_dir()
        assert progress is watcher

    def test_the_audio_step_writes_beside_the_clip(self, state, steps, watcher):
        run_export(state, watcher)

        _audio_state, audio_out, _progress = steps["audio"].calls[0]
        assert audio_out.parent == audio_dir()
        assert audio_out.suffix == ".mp3"

    def test_all_three_outputs_take_the_session_name(self, state, steps, watcher):
        state.session_name = "second pass"

        run_export(state, watcher)

        assert steps["raw"].calls[0][1].stem == "second pass"
        assert steps["post"].calls[0][2].stem == "second pass"
        assert steps["audio"].calls[0][1].stem == "second pass"

    def test_a_session_name_that_cannot_be_a_filename_is_sanitized(
        self, state, steps, watcher
    ):
        state.session_name = "take 1: second pass"

        run_export(state, watcher)

        assert steps["raw"].calls[0][1].stem == "take 1_ second pass"


class TestWhatItReports:
    def test_it_starts_every_bar_at_zero_and_names_each_step(
        self, state, steps, watcher
    ):
        run_export(state, watcher)

        assert watcher.stages == [
            "preparing export", "clipping", "fixing the loop", "pulling audio",
        ]
        assert watcher.clips == [0.0, 1.0]
        assert watcher.fixes == [0.0, 1.0]
        assert watcher.audios == [0.0, 1.0]

    def test_a_finished_run_names_the_clip_it_wrote(self, state, steps, watcher):
        ok, message = run_export(state, watcher)

        assert ok is True
        assert str(clips_dir()) in message


class TestFailures:
    def test_a_failed_clip_stops_the_run_and_reports_why(self, state, steps, watcher):
        steps["raw"].ok = False
        steps["raw"].detail = "ffmpeg not found on PATH"

        assert run_export(state, watcher) == (False, "ffmpeg not found on PATH")
        assert not steps["post"].called
        assert not steps["audio"].called

    def test_a_failed_post_process_stops_before_the_audio(self, state, steps, watcher):
        steps["post"].ok = False
        steps["post"].detail = "the bridge is too long"

        assert run_export(state, watcher) == (False, "the bridge is too long")
        assert not steps["audio"].called

    def test_a_failed_audio_pull_is_reported(self, state, steps, watcher):
        steps["audio"].ok = False
        steps["audio"].detail = "no audio stream"

        assert run_export(state, watcher) == (False, "no audio stream")

    def test_a_step_that_raises_is_reported_rather_than_lost(self, state, steps, watcher):
        def explode(*_args):
            raise RuntimeError("the disk went away")

        with patch("clipper.export_steps.export_raw_clip", explode):
            assert run_export(state, watcher) == (False, "the disk went away")


class TestVrExportPath:
    def test_a_non_vr_clip_lands_in_the_clips_folder(self, state, steps, watcher):
        state.vr = False

        run_export(state, watcher)

        assert steps["post"].calls[0][2].parent == clips_dir()

    def test_a_vr_clip_lands_in_the_vr_clips_folder(self, state, steps, watcher):
        state.vr = True

        run_export(state, watcher)

        assert steps["post"].calls[0][2].parent == vr_clips_dir()


class TestALoopedClipsRecord:
    """The loop fix stamps the clip from inside its own run, whose code is what
    made it -- which is not always the code this window was opened on."""

    def test_the_export_leaves_the_stamp_the_loop_fix_wrote(
        self, state, steps, watcher, recorded_cut
    ):
        def loop_fix(_state, _raw_path, clip_path, _progress):
            record_provenance(clip_path, recipe="clip_postprocess", recipe_version="3")
            return True, str(clip_path)

        with patch("clipper.export_steps.run_clip_postprocess", loop_fix):
            run_export(state, watcher)

        recorded = recorded_cut(state.session_name)
        assert (recorded["recipe"], recorded["recipe_version"]) == ("clip_postprocess", "3")


class TestSkipPostprocess:
    """A whole-video export is already a loop; it does not want the seam pass."""

    @pytest.fixture(autouse=True)
    def _skipping(self, state):
        state.skip_postprocess = True

    def test_the_post_process_step_never_runs(self, state, steps, watcher):
        run_export(state, watcher)

        assert not steps["post"].called

    def test_the_clip_is_written_straight_into_the_clips_folder(
        self, state, steps, watcher
    ):
        run_export(state, watcher)

        assert steps["raw"].calls[0][1].parent == clips_dir()

    def test_the_skipped_stage_still_reports_itself_finished(
        self, state, steps, watcher
    ):
        run_export(state, watcher)

        assert watcher.fixes == [0.0, 1.0]

    def test_the_audio_is_still_pulled(self, state, steps, watcher):
        run_export(state, watcher)

        assert steps["audio"].called

    def test_the_clip_says_clipper_made_it_and_that_no_recipe_did(
        self, state, steps, watcher, recorded_cut
    ):
        """Nothing but the cut touched it, so a sweep for clips made before a
        change to the loop fix finds nothing here to remake."""
        run_export(state, watcher)

        recorded = recorded_cut(state.session_name)
        assert (recorded["app"], recorded["recipe"], recorded["recipe_version"]) == (
            "clipper", None, None,
        )
