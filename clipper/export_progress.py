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
