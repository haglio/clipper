"""Tests for clipper.gui.export_worker — the QThread that runs an export.

What the export itself does -- the order of the steps, where each output lands,
what a failed one means -- is `tests/test_export_pipeline.py`, which drives it
with no thread and no window.  What is left here is the worker's own job: run
that off the Qt thread and turn what it answers into signals.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from clipper.gui.export_worker import ExportWorker


@pytest.fixture
def state(make_state):
    return make_state(
        path="C:/fake/video.mp4", session_path="C:/fake/session.json",
        total_frames=300, loaded_end=299, active_start=10, active_end=50,
        current=10, base_step=1,
    )


class _Step:
    """A stand-in for an export step: reports progress the way the real step
    does, and answers that it worked.
    """

    def __init__(self, *, stage: str, reports: str):
        self.stage_text = stage
        self.reports = reports

    def __call__(self, *args):
        progress = args[-1]
        progress.stage(self.stage_text)
        getattr(progress, self.reports)(1.0)
        return True, "written.mp4"


@pytest.fixture
def steps():
    """The three export steps, stubbed at the module they are called through."""
    with patch("clipper.export_steps.export_raw_clip",
               _Step(stage="clipping", reports="clip")), \
         patch("clipper.export_steps.run_clip_postprocess",
               _Step(stage="fixing the loop", reports="fix")), \
         patch("clipper.export_steps.export_full_audio_mp3",
               _Step(stage="pulling audio", reports="audio")):
        yield


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

        # A run starts every bar from zero, so each progress signal carries
        # 0.0 and then the 1.0 its step reports.
        assert seen["stage_changed"] == [
            "preparing export", "clipping", "fixing the loop", "pulling audio",
        ]
        assert seen["clip_progress"] == [0.0, 1.0]
        assert seen["fix_progress"] == [0.0, 1.0]
        assert seen["audio_progress"] == [0.0, 1.0]
        assert len(seen["export_finished"]) == 1


class TestWhatTheRunAnswers:
    """The worker's whole job at the end: say what the export said."""

    @pytest.mark.parametrize("answer", [
        (True, "Done: clip.mp4"),
        (False, "ffmpeg not found on PATH"),
    ])
    def test_the_finished_signal_carries_what_the_export_answered(self, state, answer):
        worker = ExportWorker(state)
        seen = _recorded(worker)

        with patch("clipper.export_pipeline.run_export", return_value=answer) as export:
            worker.run()

        assert seen["export_finished"] == [answer]
        assert export.call_args.args == (state, worker)


class TestConnectExport:
    """One wiring, shared by the window and the whole-video path that has none.

    The nine lines were written out twice, lambda included; a signal wired in
    one copy and forgotten in the other would have shown as a progress bar that
    never moved on one route only.
    """

    def test_every_signal_the_worker_emits_reaches_the_dialog(self, state, steps):
        from clipper.gui.export_dialog import ExportDialog
        from clipper.gui.export_worker import connect_export

        dialog = ExportDialog()
        worker = connect_export(state, dialog)

        worker.run()  # in this thread, so the queued signals are direct

        assert dialog.stage_label.text() == "Export complete."
