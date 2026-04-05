from __future__ import annotations

import os
import subprocess
import sys
from typing import Any


def hidden_subprocess_kwargs() -> dict[str, Any]:
    if os.name != "nt" and sys.platform != "win32":
        return {}

    kwargs: dict[str, Any] = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    kwargs["startupinfo"] = startupinfo
    show_window = getattr(subprocess, "SW_HIDE", None)
    if show_window is not None:
        startupinfo.wShowWindow = show_window
    return kwargs
