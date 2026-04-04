from __future__ import annotations

import base64
import ctypes
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import load_config
from .utils import format_seconds, sanitize_name
from .vlc_prefill_paths import (
    _looks_like_vlc_title as _path_looks_like_vlc_title,
    _resolve_media_path,
    _resolve_media_path_from_title as _path_resolve_media_path_from_title,
    _strip_vlc_title_suffix,
    _timestamp_seconds_from_title as _path_timestamp_seconds_from_title,
)


@dataclass(frozen=True)
class VlcSessionPrefill:
    video_file: str
    session_name: str
    timestamp: str
    note: str


@dataclass(frozen=True)
class _VlcProbe:
    media_path: Path
    position_seconds: float | None = None


def detect_vlc_session_prefill() -> VlcSessionPrefill | None:
    probe = _detect_from_http()
    if probe is None:
        probe = _detect_from_windows()
    if probe is None:
        return None
    timestamp = format_seconds(probe.position_seconds or 0.0)
    note = (
        f"Prefilled from VLC: {probe.media_path.name} at {timestamp}."
        if probe.position_seconds is not None
        else f"Prefilled from VLC: {probe.media_path.name}. Timestamp defaulted to {timestamp}."
    )
    return VlcSessionPrefill(
        video_file=str(probe.media_path),
        session_name=sanitize_name(probe.media_path.stem),
        timestamp=timestamp,
        note=note,
    )


def _detect_from_http() -> _VlcProbe | None:
    for port in _candidate_http_ports():
        payload = _fetch_http_status(port)
        if payload is None:
            continue
        media_path = _media_path_from_http_payload(payload)
        if media_path is None:
            media_path = _current_media_path_from_playlist(port)
        if media_path is None:
            continue
        return _VlcProbe(media_path=media_path, position_seconds=_http_time_seconds(payload))
    return None


def _detect_from_windows() -> _VlcProbe | None:
    for title in _ordered_vlc_window_titles():
        media_path = _resolve_media_path_from_title(title)
        if media_path is None:
            continue
        return _VlcProbe(media_path=media_path, position_seconds=_timestamp_seconds_from_title(title))
    return None


def _current_media_path_from_playlist(port: int) -> Path | None:
    data = _fetch_playlist_xml(port)
    if data is None:
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    for leaf in root.iter("leaf"):
        if leaf.get("current") == "current":
            uri = leaf.get("uri")
            if uri:
                return _resolve_media_path(uri)
    return None


def _fetch_playlist_xml(port: int) -> bytes | None:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/requests/playlist.xml")
    password = _vlc_http_password()
    if password:
        token = base64.b64encode(f":{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=0.5) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _candidate_http_ports() -> list[int]:
    ports = [8080]
    try:
        config = load_config()
    except Exception:
        return ports
    for port in (config.controller.vlc2_http_port, config.controller.vlc3_http_port):
        if port not in ports:
            ports.append(port)
    return ports


def _fetch_http_status(port: int) -> ET.Element | None:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/requests/status.xml")
    password = _vlc_http_password()
    if password:
        token = base64.b64encode(f":{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=0.2) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        return ET.fromstring(payload)
    except ET.ParseError:
        return None


def _media_path_from_http_payload(payload: ET.Element) -> Path | None:
    info = payload.find("./information/category[@name='meta']")
    if info is None:
        return None
    raw = (
        _text_of(info.find("./info[@name='url']"))
        or _text_of(info.find("./info[@name='filename']"))
        or _text_of(info.find("./info[@name='title']"))
    )
    return _resolve_media_path(raw)


def _http_time_seconds(payload: ET.Element) -> float | None:
    raw = _text_of(payload.find("./time"))
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _ordered_vlc_window_titles() -> list[str]:
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    titles: list[str] = []
    seen: set[str] = set()
    foreground = user32.GetForegroundWindow()

    def append_title(hwnd: int) -> None:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not _looks_like_vlc_title(title) or title in seen:
            return
        seen.add(title)
        titles.append(title)

    if foreground:
        append_title(foreground)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        append_title(hwnd)
        return True

    user32.EnumWindows(enum_proc, 0)
    return titles


def _looks_like_vlc_title(title: str) -> bool:
    return _path_looks_like_vlc_title(title)


def _timestamp_seconds_from_title(title: str) -> float | None:
    return _path_timestamp_seconds_from_title(title)


def _resolve_media_path_from_title(title: str) -> Path | None:
    return _path_resolve_media_path_from_title(title)


def _text_of(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


@lru_cache(maxsize=1)
def _vlc_http_password() -> str | None:
    return (
        os.environ.get("FUN_TIME_VLC_HTTP_PASS")
        or os.environ.get("VLC_HTTP_PASSWORD")
        or _vlc_http_password_from_config()
    )


def _vlc_http_password_from_config() -> str | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    vlcrc = Path(appdata) / "vlc" / "vlcrc"
    try:
        with vlcrc.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("http-password="):
                    value = stripped.split("=", 1)[1].strip()
                    return value or None
    except OSError:
        return None
    return None
