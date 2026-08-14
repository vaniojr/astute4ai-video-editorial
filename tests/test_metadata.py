from datetime import date

import pytest
import yt_dlp

from app import metadata as metadata_module
from app.metadata import MetadataError, fetch_metadata


class _FakeYoutubeDL:
    def __init__(self, info=None, raise_error=None):
        self._info = info
        self._raise_error = raise_error

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=False):
        if self._raise_error is not None:
            raise self._raise_error
        return self._info


def _patch_youtube_dl(monkeypatch, info=None, raise_error=None):
    monkeypatch.setattr(
        metadata_module.yt_dlp,
        "YoutubeDL",
        lambda opts: _FakeYoutubeDL(info=info, raise_error=raise_error),
    )


def test_fetch_metadata_maps_fields(monkeypatch):
    info = {
        "id": "7xgE4ZHNWRU",
        "title": "Podcast 3 Irmãos #1033",
        "channel": "Podcast 3 Irmãos",
        "upload_date": "20260812",
        "duration": 6300.0,
    }
    _patch_youtube_dl(monkeypatch, info=info)

    result = fetch_metadata("https://www.youtube.com/watch?v=7xgE4ZHNWRU")

    assert result.platform == "youtube"
    assert result.source_id == "7xgE4ZHNWRU"
    assert result.title == "Podcast 3 Irmãos #1033"
    assert result.channel == "Podcast 3 Irmãos"
    assert result.published_at == date(2026, 8, 12)
    assert result.duration_seconds == 6300


def test_fetch_metadata_falls_back_to_uploader_when_channel_missing(monkeypatch):
    info = {
        "id": "abc123",
        "title": "Título",
        "upload_date": None,
        "duration": None,
        "uploader": "Canal Uploader",
    }
    _patch_youtube_dl(monkeypatch, info=info)

    result = fetch_metadata("https://www.youtube.com/watch?v=abc123")

    assert result.channel == "Canal Uploader"
    assert result.published_at is None
    assert result.duration_seconds is None


def test_fetch_metadata_raises_actionable_error_on_missing_id(monkeypatch):
    _patch_youtube_dl(monkeypatch, info={"title": "Sem ID"})

    with pytest.raises(MetadataError):
        fetch_metadata("https://www.youtube.com/watch?v=invalid")


def test_fetch_metadata_raises_actionable_error_on_missing_title(monkeypatch):
    _patch_youtube_dl(monkeypatch, info={"id": "abc123"})

    with pytest.raises(MetadataError):
        fetch_metadata("https://www.youtube.com/watch?v=abc123")


def test_fetch_metadata_wraps_download_error(monkeypatch):
    _patch_youtube_dl(monkeypatch, raise_error=yt_dlp.utils.DownloadError("boom"))

    with pytest.raises(MetadataError):
        fetch_metadata("https://www.youtube.com/watch?v=broken")
