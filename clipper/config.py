from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipper.content import load_content

_CONTENT = load_content()

PROJECT_DIR = Path(__file__).resolve().parent.parent


def project_roots(content: dict[str, Any] | None = None) -> tuple[Path, ...]:
    """The folders that hold the suite's sibling app checkouts, in search order.

    A *list*, because checkouts move one repo at a time: a single path leaves a
    window in which a sibling that has not moved yet is unreachable.  An overlay
    that says nothing means ``suite_root/projects``.
    """
    content = _CONTENT if content is None else content
    roots = content.get("project_roots")
    if not roots:
        return (Path(content["suite_root"]) / "projects",)
    return tuple(Path(root) for root in roots)


PROJECT_ROOTS = project_roots()


def project_dir(name: str, roots: tuple[Path, ...] | None = None) -> Path:
    """The sibling checkout *name*, from the first root that actually holds it.

    Falls back to a path under the first root when no root does, so a sibling
    that isn't installed surfaces as the caller's own missing-file error rather
    than as an import-time crash here.
    """
    roots = PROJECT_ROOTS if roots is None else roots
    for root in roots:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return roots[0] / name


# Sibling checkout, outside this repo; its location is private.
_FUN_TIME_DIR = project_dir("fun_time")
DEFAULT_CONFIG_PATH = _FUN_TIME_DIR / "fun_time_config.json"


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _require_dict(parent: dict[str, Any], key: str, source_path: Path) -> dict[str, Any]:
    """A top-level section, by name. Nesting went with the layout config."""
    dotted = f"config.{key}"
    value = parent.get(key)
    if value is None:
        raise ValueError(f"Missing required config section: {dotted} (in {source_path})")
    if not isinstance(value, dict):
        raise TypeError(f"Expected object for config section: {dotted} (in {source_path})")
    return value


def _require_value(parent: dict[str, Any], key: str, source_path: Path, context: str) -> Any:
    value = parent.get(key)
    dotted = f"{context}.{key}"
    if value is None:
        raise ValueError(f"Missing required config value: {dotted} (in {source_path})")
    return value


# What clipper reads out of fun_time's config file, and nothing else.  The
# folders VLC plays from, so a title seen in a VLC window can be resolved to a
# file, and the two VLC HTTP ports to ask which file is playing.  fun_time's
# other sections -- broker, genau, audio_companion, random_favs_browser, the
# monitor layout -- describe apps clipper does not talk to, and requiring them
# meant a key clipper never reads could cost it its prefill.
@dataclass(frozen=True)
class PathsConfig:
    primary_vlc_dirs: tuple[Path, ...]
    portrait_dirs: tuple[Path, ...]
    landscape_dirs: tuple[Path, ...]
    weird_dir: Path


@dataclass(frozen=True)
class ControllerConfig:
    vlc2_http_port: int
    vlc3_http_port: int


@dataclass(frozen=True)
class ProjectConfig:
    paths: PathsConfig
    controller: ControllerConfig


def _resolve_config_path(config_path: str | Path | None) -> Path:
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = (_FUN_TIME_DIR / path).resolve()
    return path


def _require_path_value(parent: dict[str, Any], key: str, source_path: Path, context: str) -> Path:
    return _resolve_path(_FUN_TIME_DIR, _require_value(parent, key, source_path, context))


def _require_int_value(parent: dict[str, Any], key: str, source_path: Path, context: str) -> int:
    """A port, cast: fun_time writes some of these as strings."""
    return int(_require_value(parent, key, source_path, context))


def _load_paths_config(paths_raw: dict[str, Any], source_path: Path) -> PathsConfig:
    primary_vlc_dirs_raw = _require_value(paths_raw, "primary_vlc_dirs", source_path, "config.paths")
    if not isinstance(primary_vlc_dirs_raw, list):
        raise TypeError("paths.primary_vlc_dirs must be a list of folder paths")
    if not primary_vlc_dirs_raw:
        raise ValueError("paths.primary_vlc_dirs must include at least one folder path")

    return PathsConfig(
        primary_vlc_dirs=tuple(_resolve_path(_FUN_TIME_DIR, str(value)) for value in primary_vlc_dirs_raw),
        portrait_dirs=_load_dir_list(paths_raw, "portrait_dirs", "portrait_dir", source_path),
        landscape_dirs=_load_dir_list(paths_raw, "landscape_dirs", "landscape_dir", source_path),
        weird_dir=_require_path_value(paths_raw, "weird_dir", source_path, "config.paths"),
    )


def _load_controller_config(controller_raw: dict[str, Any], source_path: Path) -> ControllerConfig:
    return ControllerConfig(
        vlc2_http_port=_require_int_value(controller_raw, "vlc2_http_port", source_path, "config.controller"),
        vlc3_http_port=_require_int_value(controller_raw, "vlc3_http_port", source_path, "config.controller"),
    )


def load_config(config_path: str | Path | None = None) -> ProjectConfig:
    path = _resolve_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        raw: dict[str, Any] = json.load(fp)

    return ProjectConfig(
        paths=_load_paths_config(_require_dict(raw, "paths", path), path),
        controller=_load_controller_config(_require_dict(raw, "controller", path), path),
    )


def _load_dir_list(paths_raw: dict[str, Any], list_key: str, single_key: str, source_path: Path) -> tuple[Path, ...]:
    values = paths_raw.get(list_key)
    if values is None:
        return (_resolve_path(_FUN_TIME_DIR, str(_require_value(paths_raw, single_key, source_path, "config.paths"))),)
    if not isinstance(values, list):
        raise TypeError(f"paths.{list_key} must be a list of folder paths")
    if not values:
        raise ValueError(f"paths.{list_key} must include at least one folder path")
    return tuple(_resolve_path(_FUN_TIME_DIR, str(value)) for value in values)
