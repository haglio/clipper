"""Where the sibling app checkouts are, and how config finds them.

``suite_root`` named two things at once -- the folder holding the media library
and the folder holding the sibling apps -- and those came apart when the repos
were moved out of the file-synced tree the library stays in. The library still
reaches the code through ``suite_root``; the checkouts get their own setting.
"""

from pathlib import Path

import pytest

from clipper import config


class TestProjectRoots:
    def test_defaults_to_the_projects_folder_under_the_suite_root(self):
        """An overlay with no project_roots behaves exactly as it always did."""
        assert config.project_roots({"suite_root": "S:/suite"}) == (Path("S:/suite/projects"),)

    def test_an_empty_list_falls_back_to_the_default_too(self):
        content = {"suite_root": "S:/suite", "project_roots": []}

        assert config.project_roots(content) == (Path("S:/suite/projects"),)

    def test_reads_the_roots_from_the_overlay_in_the_order_given(self):
        content = {"suite_root": "S:/suite", "project_roots": ["W:/work", "S:/suite/projects"]}

        assert config.project_roots(content) == (Path("W:/work"), Path("S:/suite/projects"))


class TestProjectDir:
    def test_finds_a_checkout_in_the_only_root(self, tmp_path):
        checkout = tmp_path / "suite" / "alpha_app"
        checkout.mkdir(parents=True)

        assert config.project_dir("alpha_app", (tmp_path / "suite",)) == checkout

    def test_prefers_the_earlier_root_when_both_hold_the_checkout(self, tmp_path):
        moved = tmp_path / "work" / "alpha_app"
        moved.mkdir(parents=True)
        (tmp_path / "old" / "alpha_app").mkdir(parents=True)

        found = config.project_dir("alpha_app", (tmp_path / "work", tmp_path / "old"))

        assert found == moved

    def test_falls_through_to_a_later_root_for_a_checkout_that_has_not_moved(self, tmp_path):
        (tmp_path / "work" / "alpha_app").mkdir(parents=True)
        stayed = tmp_path / "old" / "beta_app"
        stayed.mkdir(parents=True)

        found = config.project_dir("beta_app", (tmp_path / "work", tmp_path / "old"))

        assert found == stayed

    def test_returns_a_path_under_the_first_root_when_no_root_holds_it(self, tmp_path):
        """Resolving must not raise: the caller reports a missing config file itself."""
        found = config.project_dir("gamma_app", (tmp_path / "work", tmp_path / "old"))

        assert found == tmp_path / "work" / "gamma_app"

    def test_a_file_of_that_name_does_not_count_as_the_checkout(self, tmp_path):
        (tmp_path / "work").mkdir()
        (tmp_path / "work" / "alpha_app").write_text("not a checkout", encoding="utf-8")
        checkout = tmp_path / "old" / "alpha_app"
        checkout.mkdir(parents=True)

        found = config.project_dir("alpha_app", (tmp_path / "work", tmp_path / "old"))

        assert found == checkout


class TestFunTimeDirComesFromTheRoots:
    def test_the_default_config_path_sits_under_a_project_root(self):
        assert any(
            config.DEFAULT_CONFIG_PATH.is_relative_to(root) for root in config.PROJECT_ROOTS
        ), f"{config.DEFAULT_CONFIG_PATH} is under none of {config.PROJECT_ROOTS}"

    def test_a_relative_config_path_still_resolves_against_the_fun_time_checkout(self):
        """load_config's relative-path branch reads the same resolved checkout."""
        resolved = config._resolve_config_path("fun_time_config.json")

        assert resolved.parent == config.DEFAULT_CONFIG_PATH.parent

    def test_a_missing_config_file_is_reported_as_such_not_as_a_resolution_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            config.load_config(tmp_path / "nope" / "fun_time_config.json")
