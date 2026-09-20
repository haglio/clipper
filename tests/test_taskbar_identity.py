"""Clipper's window groups under its pinned taskbar shortcut."""
from __future__ import annotations

import sys

from clipper import app


def test_the_pin_is_stamped_with_the_identity_the_process_claims(monkeypatch):
    claimed: list[str] = []
    stamped: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(app, "set_app_user_model_id", claimed.append)
    monkeypatch.setattr(app, "stamp_pinned_shortcuts",
                        lambda app_id, names: stamped.append((app_id, tuple(names))) or {})

    app._set_windows_app_user_model_id()

    assert claimed == [app.APP_USER_MODEL_ID]
    assert stamped == [(app.APP_USER_MODEL_ID, ("Clipper",))]


def test_a_process_windows_refuses_an_identity_still_stamps_its_pin(monkeypatch):
    stamped: list[str] = []

    def refuse(app_id: str) -> None:
        raise OSError("SetCurrentProcessExplicitAppUserModelID failed: HRESULT 0x80070057")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(app, "set_app_user_model_id", refuse)
    monkeypatch.setattr(app, "stamp_pinned_shortcuts",
                        lambda app_id, names: stamped.append(app_id) or {})

    app._set_windows_app_user_model_id()

    assert stamped == [app.APP_USER_MODEL_ID]
