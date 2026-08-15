from pathlib import Path

from app.config import load_settings


def test_load_settings_defaults(monkeypatch):
    for var in (
        "VIDEO_EDITORIAL_PROJETOS_DIR",
        "VIDEO_EDITORIAL_WHISPER_MODEL",
        "VIDEO_EDITORIAL_WHISPER_LANGUAGE",
        "VIDEO_EDITORIAL_FFMPEG_CRF",
        "VIDEO_EDITORIAL_FFMPEG_PRESET",
        "VIDEO_EDITORIAL_AUDIO_BITRATE_KBPS",
        "VIDEO_EDITORIAL_OUTPUT_FORMAT",
        "VIDEO_EDITORIAL_MAX_VIDEO_HEIGHT",
        "VIDEO_EDITORIAL_ANALYSIS_PROVIDER",
        "VIDEO_EDITORIAL_ANALYSIS_MODEL",
        "VIDEO_EDITORIAL_ANALYSIS_TEMPERATURE",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings()

    assert settings.projetos_dir == Path("projetos")
    assert settings.whisper_model == "medium"
    assert settings.whisper_language == "pt"
    assert settings.ffmpeg_crf == 18
    assert settings.ffmpeg_preset == "medium"
    assert settings.audio_bitrate_kbps == 192
    assert settings.output_format == "mp4"
    assert settings.max_video_height is None
    assert settings.analysis_provider == "claude"
    assert settings.analysis_model == "claude-sonnet-5"
    assert settings.analysis_temperature == 0.0


def test_load_settings_reads_env_var_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "outros-projetos"))
    monkeypatch.setenv("VIDEO_EDITORIAL_WHISPER_MODEL", "tiny")
    monkeypatch.setenv("VIDEO_EDITORIAL_WHISPER_LANGUAGE", "en")
    monkeypatch.setenv("VIDEO_EDITORIAL_FFMPEG_CRF", "23")
    monkeypatch.setenv("VIDEO_EDITORIAL_FFMPEG_PRESET", "fast")
    monkeypatch.setenv("VIDEO_EDITORIAL_AUDIO_BITRATE_KBPS", "128")
    monkeypatch.setenv("VIDEO_EDITORIAL_OUTPUT_FORMAT", "mov")
    monkeypatch.setenv("VIDEO_EDITORIAL_MAX_VIDEO_HEIGHT", "1080")
    monkeypatch.setenv("VIDEO_EDITORIAL_ANALYSIS_PROVIDER", "claude")
    monkeypatch.setenv("VIDEO_EDITORIAL_ANALYSIS_MODEL", "claude-opus-5")
    monkeypatch.setenv("VIDEO_EDITORIAL_ANALYSIS_TEMPERATURE", "0.5")

    settings = load_settings()

    assert settings.projetos_dir == tmp_path / "outros-projetos"
    assert settings.whisper_model == "tiny"
    assert settings.whisper_language == "en"
    assert settings.ffmpeg_crf == 23
    assert settings.ffmpeg_preset == "fast"
    assert settings.audio_bitrate_kbps == 128
    assert settings.output_format == "mov"
    assert settings.max_video_height == 1080
    assert settings.analysis_provider == "claude"
    assert settings.analysis_model == "claude-opus-5"
    assert settings.analysis_temperature == 0.5
