"""What clipper's copy of the fun_time config parser refuses to load.

`config.py` is a 225-statement parser for a file clipper does not own, and it is
guarded by neither the dead-code gate (the whole file is exempt) nor a test of
its actual job: making every `_require_*` helper return None instead of raising
left the whole suite green, which means a malformed or half-written
`fun_time_config.json` would reach the app as a config full of Nones rather than
as the error the parser exists to raise.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipper import config


def _without(cfg_path: Path, *keys: str) -> Path:
    """Rewrite the config with a dotted key removed."""
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    for dotted in keys:
        target = raw
        *parents, leaf = dotted.split(".")
        for part in parents:
            target = target[part]
        del target[leaf]
    cfg_path.write_text(json.dumps(raw), encoding="utf-8")
    return cfg_path


def _replacing(cfg_path: Path, dotted: str, value) -> Path:
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    target = raw
    *parents, leaf = dotted.split(".")
    for part in parents:
        target = target[part]
    target[leaf] = value
    cfg_path.write_text(json.dumps(raw), encoding="utf-8")
    return cfg_path


class TestALoadableConfig:
    def test_the_values_come_through_as_the_types_the_app_uses(self, cfg_path: Path):
        cfg = config.load_config(cfg_path)

        assert (cfg.controller.vlc2_http_port, cfg.controller.vlc3_http_port) == (8091, 8092)
        assert cfg.paths.weird_dir == Path(cfg_path.parent / "weird")
        assert cfg.paths.primary_vlc_dirs == (Path(cfg_path.parent / "vlc_primary"),)

    def test_a_number_written_as_a_string_is_cast_to_the_declared_type(self, cfg_path: Path):
        cfg = config.load_config(_replacing(cfg_path, "controller.vlc2_http_port", "9600"))

        assert cfg.controller.vlc2_http_port == 9600

    @pytest.mark.parametrize(
        "dotted",
        ["broker", "genau", "audio_companion", "controller.layout",
         "controller.primary_vlc_http_port", "paths.clips_dir", "paths.vlc_exe"],
    )
    def test_a_key_clipper_does_not_read_is_not_required(self, cfg_path: Path, dotted):
        """clipper parses fun_time's file; it must not police the half it ignores.

        Every one of these used to raise, and both call sites swallow the raise
        and fall back -- so a fun_time config missing a key about a serial port
        cost clipper its VLC prefill.
        """
        cfg = config.load_config(_without(cfg_path, dotted))

        assert cfg.controller.vlc2_http_port == 8091

    def test_a_config_file_that_is_not_there_names_itself(self, tmp_path: Path):
        missing = tmp_path / "no_such_config.json"

        with pytest.raises(FileNotFoundError, match="no_such_config.json"):
            config.load_config(missing)


class TestMissingSections:
    @pytest.mark.parametrize("section", ["paths", "controller"])
    def test_a_missing_section_names_the_section_and_the_file(self, cfg_path: Path, section):
        with pytest.raises(ValueError) as raised:
            config.load_config(_without(cfg_path, section))

        assert f"config.{section}" in str(raised.value)
        assert str(cfg_path) in str(raised.value)

    @pytest.mark.parametrize("section", ["paths", "controller"])
    def test_a_section_that_is_not_an_object_is_a_type_error(self, cfg_path: Path, section):
        with pytest.raises(TypeError) as raised:
            config.load_config(_replacing(cfg_path, section, "not a section"))

        assert f"config.{section}" in str(raised.value)


class TestMissingValues:
    @pytest.mark.parametrize("dotted", [
        "paths.weird_dir",
        "controller.vlc2_http_port",
        "controller.vlc3_http_port",
    ])
    def test_a_missing_value_names_its_dotted_path_and_the_file(self, cfg_path: Path, dotted):
        with pytest.raises(ValueError) as raised:
            config.load_config(_without(cfg_path, dotted))

        assert f"config.{dotted}" in str(raised.value)
        assert str(cfg_path) in str(raised.value)


class TestPrimaryVlcDirs:
    def test_an_empty_list_of_folders_is_refused(self, cfg_path: Path):
        with pytest.raises(ValueError, match="at least one folder path"):
            config.load_config(_replacing(cfg_path, "paths.primary_vlc_dirs", []))

    def test_a_single_folder_written_as_a_string_is_refused(self, cfg_path: Path):
        with pytest.raises(TypeError, match="must be a list of folder paths"):
            config.load_config(_replacing(cfg_path, "paths.primary_vlc_dirs", "S:/one"))

    def test_the_folders_keep_the_order_they_were_written_in(self, cfg_path: Path):
        cfg = config.load_config(
            _replacing(cfg_path, "paths.primary_vlc_dirs", ["S:/second", "S:/first"])
        )

        assert [p.name for p in cfg.paths.primary_vlc_dirs] == ["second", "first"]


class TestTheDirListsFallBackToTheSingularKey:
    """fun_time's older spelling: one ``portrait_dir`` instead of a list."""

    def test_the_singular_key_is_read_when_the_list_is_absent(self, cfg_path: Path):
        cfg = config.load_config(cfg_path)

        assert [p.name for p in cfg.paths.portrait_dirs] == ["portrait"]
        assert [p.name for p in cfg.paths.landscape_dirs] == ["landscape"]

    def test_the_list_wins_when_both_are_written(self, cfg_path: Path):
        cfg = config.load_config(
            _replacing(cfg_path, "paths.portrait_dirs", ["S:/tall", "S:/taller"])
        )

        assert [p.name for p in cfg.paths.portrait_dirs] == ["tall", "taller"]

    def test_neither_spelling_present_names_the_singular_key(self, cfg_path: Path):
        with pytest.raises(ValueError, match=r"config\.paths\.portrait_dir"):
            config.load_config(_without(cfg_path, "paths.portrait_dir"))
