"""Tests for clipper.gui.export_worker — QThread-based export."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from clipper.gui.export_worker import ExportWorker
from clipper.paths import AUDIO_DIR, CLIPS_DIR, RAW_CLIPS_DIR, VR_CLIPS_DIR
from clipper.state import ExportJob


@pytest.fixture()
def state(make_state):
    return make_state(
        path="C:/fake/video.mp4", session_path="C:/fake/session.json",
        total_frames=300, loaded_end=299, active_start=10, active_end=50,
        current=10, base_step=1,
    )


class _Step:
    """A stand-in for an export step: records its call, drives the job it is
    handed the way the real step does, and answers with whatever it is told to.
    """

    def __init__(self, *, stage: str, progress_field: str, ok: bool = True, detail: str = ""):
        self.stage = stage
        self.progress_field = progress_field
        self.ok = ok
        self.detail = detail
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)
        job = args[-1]
        job.stage = self.stage
        setattr(job, self.progress_field, 1.0)
        return self.ok, self.detail

    @property
    def called(self) -> bool:
        return bool(self.calls)


@pytest.fixture()
def steps():
    """The three export steps, stubbed at the module they are imported from."""
    stubs = {
        "raw": _Step(stage="clipping", progress_field="clip_progress", detail="raw.mp4"),
        "post": _Step(stage="fixing the loop", progress_field="fix_progress", detail="clip.mp4"),
        "audio": _Step(stage="pulling audio", progress_field="audio_progress", detail="audio.mp3"),
    }
    with patch("clipper.export_steps.export_raw_clip", stubs["raw"]), \
         patch("clipper.export_steps.run_clip_postprocess", stubs["post"]), \
         patch("clipper.export_steps.export_full_audio_mp3", stubs["audio"]):
        yield stubs


def _recorded(worker: ExportWorker) -> dict[str, list]:
    """Connect every signal the worker declares and collect what arrives."""
    seen: dict[str, list] = {}
    for name in ("stage_changed", "clip_progress", "fix_progress",
                 "audio_progress", "export_finished"):
        seen[name] = []
        getattr(worker, name).connect(
            lambda *args, _name=name: seen[_name].append(args if len(args) > 1 else args[0])
        )
    return seen


class TestSignals:
    """Every signal is connected and emitted during a run.

    The old test asserted the five names were keys of `ExportWorker.__dict__`,
    which a declaration satisfies and a run that never emits also satisfies.
    """

    def test_a_run_emits_every_signal_the_worker_declares(self, state, steps):
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        # The job resets each field as it is built, so every progress signal
        # starts at 0.0 and the run drives it to 1.0.
        assert seen["stage_changed"] == [
            "preparing export", "clipping", "fixing the loop", "pulling audio",
        ]
        assert seen["clip_progress"] == [0.0, 1.0]
        assert seen["fix_progress"] == [0.0, 1.0]
        assert seen["audio_progress"] == [0.0, 1.0]
        assert len(seen["export_finished"]) == 1


class TestRunCallsExportSteps:
    def test_the_raw_clip_step_gets_the_state_an_output_path_and_the_job(self, state, steps):
        ExportWorker(state).run()

        clip_state, out_path, job = steps["raw"].calls[0]
        assert clip_state is state
        assert out_path.parent == RAW_CLIPS_DIR
        assert isinstance(job, ExportJob)

    def test_the_post_process_step_gets_the_raw_input_and_the_clip_output(self, state, steps):
        ExportWorker(state).run()

        post_state, raw_in, clip_out, job = steps["post"].calls[0]
        assert post_state is state
        assert raw_in == steps["raw"].calls[0][1]
        assert clip_out.parent == CLIPS_DIR
        assert isinstance(job, ExportJob)

    def test_the_audio_step_writes_beside_the_clip(self, state, steps):
        ExportWorker(state).run()

        _audio_state, audio_out, _job = steps["audio"].calls[0]
        assert audio_out.parent == AUDIO_DIR
        assert audio_out.suffix == ".mp3"

    def test_all_three_outputs_take_the_session_name(self, state, steps):
        state.session_name = "second pass"

        ExportWorker(state).run()

        assert steps["raw"].calls[0][1].stem == "second pass"
        assert steps["post"].calls[0][2].stem == "second pass"
        assert steps["audio"].calls[0][1].stem == "second pass"

    def test_a_session_name_that_cannot_be_a_filename_is_sanitized(self, state, steps):
        state.session_name = "take 1: second pass"

        ExportWorker(state).run()

        assert steps["raw"].calls[0][1].stem == "take 1_ second pass"


class TestFailures:
    def test_a_failed_clip_stops_the_run_and_reports_why(self, state, steps):
        steps["raw"].ok = False
        steps["raw"].detail = "ffmpeg not found on PATH"
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        assert seen["export_finished"] == [(False, "ffmpeg not found on PATH")]
        assert not steps["post"].called
        assert not steps["audio"].called

    def test_a_failed_post_process_stops_before_the_audio(self, state, steps):
        steps["post"].ok = False
        steps["post"].detail = "the bridge is too long"
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        assert seen["export_finished"] == [(False, "the bridge is too long")]
        assert not steps["audio"].called

    def test_a_failed_audio_pull_is_reported(self, state, steps):
        steps["audio"].ok = False
        steps["audio"].detail = "no audio stream"
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        assert seen["export_finished"] == [(False, "no audio stream")]

    def test_a_step_that_raises_is_reported_rather_than_lost(self, state, steps):
        def explode(*args):
            raise RuntimeError("the disk went away")

        worker = ExportWorker(state)
        seen = _recorded(worker)
        with patch("clipper.export_steps.export_raw_clip", explode):
            worker.run()

        assert seen["export_finished"] == [(False, "the disk went away")]

    def test_a_finished_run_names_the_clip_it_wrote(self, state, steps):
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        ok, message = seen["export_finished"][0]
        assert ok is True
        assert str(CLIPS_DIR) in message


class TestVrExportPath:
    def test_a_non_vr_clip_lands_in_the_clips_folder(self, state, steps):
        state.vr = False

        ExportWorker(state).run()

        assert steps["post"].calls[0][2].parent == CLIPS_DIR

    def test_a_vr_clip_lands_in_the_vr_clips_folder(self, state, steps):
        state.vr = True

        ExportWorker(state).run()

        assert steps["post"].calls[0][2].parent == VR_CLIPS_DIR


class TestSkipPostprocess:
    """A whole-video export is already a loop; it does not want the seam pass."""

    @pytest.fixture(autouse=True)
    def _skipping(self, state):
        state.skip_postprocess = True

    def test_the_post_process_step_never_runs(self, state, steps):
        ExportWorker(state).run()

        assert not steps["post"].called

    def test_the_clip_is_written_straight_into_the_clips_folder(self, state, steps):
        ExportWorker(state).run()

        assert steps["raw"].calls[0][1].parent == CLIPS_DIR

    def test_the_skipped_stage_still_reports_itself_finished(self, state, steps):
        worker = ExportWorker(state)
        seen = _recorded(worker)

        worker.run()

        assert seen["fix_progress"] == [0.0, 1.0]

    def test_the_audio_is_still_pulled(self, state, steps):
        ExportWorker(state).run()

        assert steps["audio"].called
