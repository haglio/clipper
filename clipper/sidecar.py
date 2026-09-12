from __future__ import annotations

import logging
from pathlib import Path

from app_support import provenance
from app_support.json_store import locked_update
from app_support.mirrored_tree import library_roots_beside, mirrored_path

from .paths import metadata_dir

logger = logging.getLogger(__name__)


def record_provenance(
    clip: Path, *, recipe: str | None = None, recipe_version: str | None = None,
) -> None:
    root = metadata_dir()
    sidecar = mirrored_path(
        clip, roots=library_roots_beside(root), mirror_root=root, suffix=".json",
    )
    if sidecar is None:
        return
    stamp = provenance.stamp(
        "clipper", anchor=__file__, recipe=recipe, recipe_version=recipe_version,
    )
    try:
        locked_update(sidecar, lambda payload: {**payload, "provenance": {"cut": stamp}})
    except (OSError, ValueError):
        logger.warning("Could not record what made %s", clip, exc_info=True)
