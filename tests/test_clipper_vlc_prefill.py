"""Tests for clipper.vlc_prefill."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from clipper.vlc_prefill import (
    VlcSessionPrefill,
    _VlcProbe,
    _current_media_path_from_playlist,
    _resolve_media_path,
    _timestamp_seconds_from_title,
    _vlc_http_password,
    _vlc_http_password_from_config,
    detect_vlc_session_prefill,
)
from clipper.vlc_prefill_paths import _strip_vlc_title_suffix


class TestDetectVlcSessionPrefill:
    def test_prefers_http_probe(self, tmp_path: Path):
        video = tmp_path / "alpha.mp4"
        video.write_bytes(b"")
        with (
            patch("clipper.vlc_prefill._detect_from_http", return_value=_VlcProbe(video, 12.5)),
            patch("clipper.vlc_prefill._detect_from_windows") as windows_probe,
        ):
            result = detect_vlc_session_prefill()

        assert result == VlcSessionPrefill(
            video_file=str(video),
            session_name="alpha",
            timestamp="00:00:12.500",
            note="Prefilled from VLC: alpha.mp4 at 00:00:12.500.",
        )
        windows_probe.assert_not_called()

    def test_defaults_timestamp_when_only_file_is_known(self, tmp_path: Path):
        video = tmp_path / "beta clip.mp4"
        video.write_bytes(b"")
        with (
            patch("clipper.vlc_prefill._detect_from_http", return_value=None),
            patch("clipper.vlc_prefill._detect_from_windows", return_value=_VlcProbe(video, None)),
        ):
            result = detect_vlc_session_prefill()

        assert result == VlcSessionPrefill(
            video_file=str(video),
            session_name="beta clip",
            timestamp="00:00:00.000",
            note="Prefilled from VLC: beta clip.mp4. Timestamp defaulted to 00:00:00.000.",
        )

    def test_http_resolves_filename_via_search_roots(self, tmp_path: Path):
        root = tmp_path / "videos"
        root.mkdir()
        video = root / "clip.mp4"
        video.write_bytes(b"")
        status_xml = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            "<root><time>3</time>"
            "<information><category name=\"meta\">"
            "<info name=\"filename\">clip.mp4</info>"
            "</category></information></root>"
        )
        with (
            patch("clipper.vlc_prefill._candidate_http_ports", return_value=[9999]),
            patch("clipper.vlc_prefill._fetch_http_status") as mock_status,
            patch("clipper.vlc_prefill_paths.search_roots", return_value=(root,)),
            patch("clipper.vlc_prefill._fetch_playlist_xml") as mock_playlist,
        ):
            import xml.etree.ElementTree as ET
            mock_status.return_value = ET.fromstring(status_xml)
            from clipper.vlc_prefill import _detect_from_http
            result = _detect_from_http()
        assert result is not None
        assert result.media_path == video
        assert result.position_seconds == 3.0
        mock_playlist.assert_not_called()

    def test_http_falls_back_to_playlist_when_status_gives_unresolvable_filename(self, tmp_path: Path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"")
        uri = video.resolve().as_uri()
        status_xml = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            "<root><time>7</time>"
            "<information><category name=\"meta\">"
            "<info name=\"filename\">clip.mp4</info>"
            "</category></information></root>"
        )
        playlist_xml = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<node><node name="Playlist">'
            f'<leaf name="clip.mp4" uri="{uri}" current="current"/>'
            '</node></node>'
        )
        with (
            patch("clipper.vlc_prefill._candidate_http_ports", return_value=[9999]),
            patch("clipper.vlc_prefill._fetch_http_status") as mock_status,
            patch("clipper.vlc_prefill_paths.search_roots", return_value=()),
            patch("clipper.vlc_prefill._fetch_playlist_xml") as mock_playlist,
        ):
            import xml.etree.ElementTree as ET
            mock_status.return_value = ET.fromstring(status_xml)
            mock_playlist.return_value = playlist_xml.encode("utf-8")
            from clipper.vlc_prefill import _detect_from_http
            result = _detect_from_http()
        assert result is not None
        assert result.media_path == video.resolve()
        assert result.position_seconds == 7.0

    def test_returns_none_when_nothing_detected(self):
        with (
            patch("clipper.vlc_prefill._detect_from_http", return_value=None),
            patch("clipper.vlc_prefill._detect_from_windows", return_value=None),
        ):
            assert detect_vlc_session_prefill() is None


class TestResolveMediaPath:
    def test_resolves_file_uri(self, tmp_path: Path):
        video = tmp_path / "gamma.mp4"
        video.write_bytes(b"")
        uri = video.resolve().as_uri()

        result = _resolve_media_path(uri)

        assert result == video.resolve()

    def test_looks_up_filename_in_search_roots(self, tmp_path: Path):
        root = tmp_path / "videos"
        root.mkdir()
        video = root / "delta.mp4"
        video.write_bytes(b"")
        with patch("clipper.vlc_prefill_paths.search_roots", return_value=(root,)):
            result = _resolve_media_path("delta.mp4")
        assert result == video


class TestTitleParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Example.mp4 - VLC media player", "Example.mp4"),
            ("Example.mp4 - VLC media player (Direct3D11 output)", "Example.mp4"),
            ("Example.mp4", "Example.mp4"),
        ],
    )
    def test_strips_known_suffixes(self, raw: str, expected: str):
        assert _strip_vlc_title_suffix(raw) == expected

    def test_extracts_timestamp_from_title(self):
        result = _timestamp_seconds_from_title("Example.mp4 01:02:03.500 - VLC media player")
        assert result == pytest.approx(3723.5)

    def test_returns_none_when_title_has_no_timestamp(self):
        assert _timestamp_seconds_from_title("Example.mp4 - VLC media player") is None


class TestPlaylistFallback:
    def test_extracts_current_uri_from_playlist(self, tmp_path: Path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"")
        uri = video.resolve().as_uri()
        playlist_xml = (
            '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>'
            '<node ro="rw" name="" id="0">'
            '<node ro="ro" name="Playlist" id="1">'
            f'<leaf ro="rw" name="clip.mp4" id="3" duration="5" uri="{uri}" current="current"/>'
            '</node></node>'
        )
        with patch("clipper.vlc_prefill._fetch_playlist_xml") as mock_fetch:
            mock_fetch.return_value = playlist_xml.encode("utf-8")
            result = _current_media_path_from_playlist(8080)
        assert result == video.resolve()

    def test_returns_none_when_no_current_item(self):
        playlist_xml = (
            '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>'
            '<node ro="rw" name="" id="0">'
            '<node ro="ro" name="Playlist" id="1">'
            '<leaf ro="rw" name="clip.mp4" id="3" duration="5" uri="file:///C:/x.mp4"/>'
            '</node></node>'
        )
        with patch("clipper.vlc_prefill._fetch_playlist_xml") as mock_fetch:
            mock_fetch.return_value = playlist_xml.encode("utf-8")
            assert _current_media_path_from_playlist(8080) is None

    def test_returns_none_when_fetch_fails(self):
        with patch("clipper.vlc_prefill._fetch_playlist_xml", return_value=None):
            assert _current_media_path_from_playlist(8080) is None


class TestVlcHttpPassword:
    def test_prefers_environment_variable(self):
        with (
            patch.dict("os.environ", {"FUN_TIME_VLC_HTTP_PASS": "env-secret"}, clear=False),
            patch("clipper.vlc_prefill._vlc_http_password_from_config", return_value="config-secret"),
        ):
            _vlc_http_password.cache_clear()
            assert _vlc_http_password() == "env-secret"
            _vlc_http_password.cache_clear()

    def test_reads_password_from_vlcrc(self, tmp_path: Path):
        appdata = tmp_path / "appdata"
        vlc_dir = appdata / "vlc"
        vlc_dir.mkdir(parents=True)
        (vlc_dir / "vlcrc").write_text("# comment\nhttp-password=from-config\n", encoding="utf-8")

        with patch.dict("os.environ", {"APPDATA": str(appdata)}, clear=False):
            assert _vlc_http_password_from_config() == "from-config"
