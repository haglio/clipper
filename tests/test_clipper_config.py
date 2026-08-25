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

        assert cfg.config_path == cfg_path
        assert cfg.controller.primary_vlc_http_port == 8090
        assert cfg.broker.baud == 115200
        assert cfg.broker.auto_stale_timeout == pytest.approx(8.0)
        assert cfg.genau.shuffle_on_load is True
        assert cfg.paths.clips_dir == Path(cfg_path.parent / "clips")

    def test_a_number_written_as_a_string_is_cast_to_the_declared_type(self, cfg_path: Path):
        cfg = config.load_config(_replacing(cfg_path, "broker.baud", "9600"))

        assert cfg.broker.baud == 9600

    def test_a_config_file_that_is_not_there_names_itself(self, tmp_path: Path):
        missing = tmp_path / "no_such_config.json"

        with pytest.raises(FileNotFoundError, match="no_such_config.json"):
            config.load_config(missing)


class TestMissingSections:
    @pytest.mark.parametrize(
        "section", ["paths", "controller", "broker", "genau", "audio_companion"]
    )
    def test_a_missing_section_names_the_section_and_the_file(self, cfg_path: Path, section):
        with pytest.raises(ValueError) as raised:
            config.load_config(_without(cfg_path, section))

        assert f"config.{section}" in str(raised.value)
        assert str(cfg_path) in str(raised.value)

    def test_a_missing_nested_section_names_its_dotted_path(self, cfg_path: Path):
        with pytest.raises(ValueError, match=r"config\.controller\.layout"):
            config.load_config(_without(cfg_path, "controller.layout"))

    @pytest.mark.parametrize("section", ["paths", "broker"])
    def test_a_section_that_is_not_an_object_is_a_type_error(self, cfg_path: Path, section):
        with pytest.raises(TypeError) as raised:
            config.load_config(_replacing(cfg_path, section, "not a section"))

        assert f"config.{section}" in str(raised.value)


class TestMissingValues:
    @pytest.mark.parametrize("dotted", [
        "paths.vlc_exe",
        "paths.clips_dir",
        "controller.primary_vlc_http_port",
        "controller.layout.primary_top_ratio",
        "broker.baud",
        "genau.udp_port",
        "audio_companion.port",
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


class TestOptionalBrowserSection:
    def test_it_is_optional(self, cfg_path: Path):
        cfg = config.load_config(cfg_path)

        assert cfg.random_favs_browser.enabled is False

    def test_the_older_chrome_overlay_key_is_still_read(self, cfg_path: Path):
        cfg = config.load_config(
            _replacing(cfg_path, "chrome_overlay", {"enabled": True, "profile_name": "Work"})
        )

        assert cfg.random_favs_browser.enabled is True
        assert cfg.random_favs_browser.profile_name == "Work"

    def test_the_newer_key_wins_over_the_older_one(self, cfg_path: Path):
        _replacing(cfg_path, "chrome_overlay", {"profile_name": "Old"})
        cfg = config.load_config(
            _replacing(cfg_path, "random_favs_browser", {"profile_name": "New"})
        )

        assert cfg.random_favs_browser.profile_name == "New"

    def test_a_browser_section_that_is_not_an_object_is_refused(self, cfg_path: Path):
        with pytest.raises(TypeError, match="random_favs_browser"):
            config.load_config(_replacing(cfg_path, "random_favs_browser", "yes please"))
