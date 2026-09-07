"""What an export step tells whoever is watching it.

Four calls, so the export steps say what they mean.  They used to write fields
on an `ExportJob` dataclass instead, and the thing that turned those writes into
Qt signals was a subclass defined *inside* `ExportWorker.run` that overrode
`__setattr__` and used `object.__setattr__` / `object.__getattribute__` to dodge
its own hook -- so what reached the dialog was decided by a name match in a
metaclass-ish trick two modules away from the code doing the writing.

No Qt here: the export steps run off the GUI thread and are kept Qt-free.
"""

from __future__ import annotations

from typing import Protocol


class ExportProgress(Protocol):
    """The progress an export reports, as calls rather than as field writes."""

    def stage(self, text: str) -> None:
        """Say which of the three steps is running."""

    def clip(self, fraction: float) -> None:
        """How far the raw clip export has got, 0.0 to 1.0."""

    def fix(self, fraction: float) -> None:
        """How far the loop post-process has got, 0.0 to 1.0."""

    def audio(self, fraction: float) -> None:
        """How far the audio extraction has got, 0.0 to 1.0."""


# The loop post-process is a subprocess, so the only way it can say how far it
# has got is to print it.  Written and read here, both: a parent and a child
# that each spell the format out is a bar that stops moving the day one of them
# is edited, and silently, because the line just stops matching.
_PROGRESS_PREFIX = "postprocess-progress"


def progress_line(fraction: float) -> str:
    """How the post-process says it has finished *fraction* of its work."""
    return f"{_PROGRESS_PREFIX} {fraction:.4f}"


def fraction_in(line: str) -> float | None:
    """The fraction that line carries, or None -- it is a line for a person.

    Everything else the script prints is its summary or an error, which the
    caller keeps for the message it shows when the run fails.
    """
    prefix, _, rest = line.partition(" ")
    if prefix != _PROGRESS_PREFIX:
        return None
    try:
        return float(rest)
    except ValueError:
        return None
