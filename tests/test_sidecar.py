from __future__ import annotations

import json
import logging

from clipper.paths import clips_dir
from clipper.sidecar import record_provenance


def test_an_exported_clip_is_recorded_where_evolver_files_that_clips_metadata(recorded_cut):
    record_provenance(clips_dir() / "scene one.mp4", recipe="a recipe", recipe_version="7")

    recorded = recorded_cut("scene one")
    assert (recorded["app"], recorded["recipe"], recorded["recipe_version"]) == (
        "clipper", "a recipe", "7",
    )


def test_what_other_apps_recorded_about_the_clip_is_kept(genau_sidecar):
    sidecar = genau_sidecar("scene one")
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps({"video": {"type": "genau_clip"}, "favorite": True}),
                       encoding="utf-8")

    record_provenance(clips_dir() / "scene one.mp4")

    recorded = json.loads(sidecar.read_text(encoding="utf-8"))
    assert (recorded["video"], recorded["favorite"]) == ({"type": "genau_clip"}, True)


def test_an_export_replaces_what_was_recorded_as_making_the_file_it_overwrote(genau_sidecar):
    """An export writes a new file at that path, so no act recorded for the one
    it replaced describes what is there now."""
    sidecar = genau_sidecar("scene one")
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps({"provenance": {"generation": {"app": "another app"}}}),
                       encoding="utf-8")

    record_provenance(clips_dir() / "scene one.mp4")

    assert list(json.loads(sidecar.read_text(encoding="utf-8"))["provenance"]) == ["cut"]


def test_a_clip_outside_the_library_is_given_no_record(library, tmp_path):
    record_provenance(tmp_path / "elsewhere" / "scene one.mp4")

    assert not (library / "videos" / "metadata").exists()


def test_a_sidecar_it_cannot_read_is_left_for_its_owner_and_the_export_goes_on(
    genau_sidecar, caplog
):
    sidecar = genau_sidecar("scene one")
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("{ not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="clipper.sidecar"):
        record_provenance(clips_dir() / "scene one.mp4")

    assert sidecar.read_text(encoding="utf-8") == "{ not json"
    assert "scene one.mp4" in caplog.text


def test_a_record_it_cannot_write_does_not_stop_the_export(library, caplog):
    (library / "videos").mkdir(parents=True)
    (library / "videos" / "metadata").write_text("a file where the folder goes", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="clipper.sidecar"):
        record_provenance(clips_dir() / "scene one.mp4")

    assert "scene one.mp4" in caplog.text
