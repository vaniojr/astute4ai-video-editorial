import yt_dlp

from app import downloader as downloader_module
from app.config import Settings
from app.downloader import DownloadError, download_video


def _settings(tmp_path, max_video_height=None):
    return Settings(
        projetos_dir=tmp_path / "projetos",
        whisper_model="medium",
        whisper_language="pt",
        ffmpeg_crf=18,
        ffmpeg_preset="medium",
        audio_bitrate_kbps=192,
        output_format="mp4",
        max_video_height=max_video_height,
        analysis_provider="claude",
        analysis_model="claude-sonnet-5",
        analysis_temperature=0.0,
        default_brand="generic",
        brands_dir=tmp_path / "brands",
        thumbnail_provider="manual",
        editorial_provider="claude",
        editorial_model="claude-sonnet-5",
        editorial_temperature=0.0,
    )


class _FakeYoutubeDL:
    def __init__(self, opts, *, raise_error=None):
        self._opts = opts
        self._raise_error = raise_error

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=False):
        if self._raise_error is not None:
            raise self._raise_error
        final_path = self._opts["outtmpl"].replace("%(ext)s", "mp4")
        with open(final_path, "wb") as fh:
            fh.write(b"fake video bytes")
        return {"id": "abc123"}


def _patch_youtube_dl(monkeypatch, raise_error=None):
    monkeypatch.setattr(
        downloader_module.yt_dlp,
        "YoutubeDL",
        lambda opts: _FakeYoutubeDL(opts, raise_error=raise_error),
    )


def _patch_ffmpeg_present(monkeypatch, present=True):
    monkeypatch.setattr(
        downloader_module.shutil, "which", lambda name: "/usr/bin/ffmpeg" if present else None
    )


def test_download_video_creates_final_file(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg_present(monkeypatch)
    _patch_youtube_dl(monkeypatch)
    project_dir = tmp_path / "projetos" / "projeto"
    project_dir.mkdir(parents=True)

    result = download_video(project_dir, "https://example.com/video", settings)

    assert result.skipped is False
    assert result.path.name == "video-original.mp4"
    assert result.path.exists()


def test_download_video_is_idempotent_by_default(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = tmp_path / "projetos" / "projeto"
    original_dir = project_dir / "original"
    original_dir.mkdir(parents=True)
    existing = original_dir / "video-original.mp4"
    existing.write_bytes(b"already here")

    def _fail_if_called(opts):
        raise AssertionError("yt-dlp não deveria ser chamado quando o arquivo já existe")

    monkeypatch.setattr(downloader_module.yt_dlp, "YoutubeDL", _fail_if_called)

    result = download_video(project_dir, "https://example.com/video", settings)

    assert result.skipped is True
    assert existing.read_bytes() == b"already here"


def test_download_video_force_redownloads(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg_present(monkeypatch)
    _patch_youtube_dl(monkeypatch)
    project_dir = tmp_path / "projetos" / "projeto"
    original_dir = project_dir / "original"
    original_dir.mkdir(parents=True)
    existing = original_dir / "video-original.mp4"
    existing.write_bytes(b"stale content")

    result = download_video(project_dir, "https://example.com/video", settings, force=True)

    assert result.skipped is False
    assert result.path.read_bytes() == b"fake video bytes"


def test_download_video_raises_when_ffmpeg_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg_present(monkeypatch, present=False)
    project_dir = tmp_path / "projetos" / "projeto"
    project_dir.mkdir(parents=True)

    try:
        download_video(project_dir, "https://example.com/video", settings)
        assert False, "deveria ter levantado DownloadError"
    except DownloadError as exc:
        assert "FFmpeg" in str(exc)


def test_download_video_wraps_download_error(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg_present(monkeypatch)
    _patch_youtube_dl(monkeypatch, raise_error=yt_dlp.utils.DownloadError("boom"))
    project_dir = tmp_path / "projetos" / "projeto"
    project_dir.mkdir(parents=True)

    try:
        download_video(project_dir, "https://example.com/video", settings)
        assert False, "deveria ter levantado DownloadError"
    except DownloadError:
        pass
