import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app import ffmpeg_utils as ffmpeg_utils_module
from app.brands import Brand, BrandAssets, BrandColors, BrandFeatures, BrandThumbnailConfig, BrandVideoConfig
from app.config import Settings
from app.editorial_models import Cta, EditorialPlan, Intro, SourceAttribution
from app.editorial_renderer import EditorialRenderError, render_editorial_video


def _settings(tmp_path):
    return Settings(
        projetos_dir=tmp_path / "projetos",
        whisper_model="tiny",
        whisper_language="pt",
        ffmpeg_crf=18,
        ffmpeg_preset="medium",
        audio_bitrate_kbps=192,
        output_format="mp4",
        max_video_height=None,
        analysis_provider="claude",
        analysis_model="claude-sonnet-5",
        analysis_temperature=0.0,
        default_brand="generic",
        brands_dir=tmp_path / "brands",
        thumbnail_provider="manual",
        editorial_provider="claude",
        editorial_model="claude-sonnet-5",
        editorial_temperature=0.0,
        editorial_intro_seconds=10.0,
        editorial_cta_seconds=5.0,
    )


def _brand(tmp_path, *, with_font=True):
    font_path = None
    assets_dir = tmp_path / "brands" / "bussola-politica" / "assets"
    if with_font:
        assets_dir.mkdir(parents=True, exist_ok=True)
        font_path = assets_dir / "font.ttf"
        font_path.write_bytes(b"fake font bytes")

    return Brand(
        slug="bussola-politica",
        name="Bússola Política",
        colors=BrandColors(background="#090909", text="#FFFFFF"),
        features=BrandFeatures(cta_enabled=True),
        assets=BrandAssets(primary_font=font_path),
        video=BrandVideoConfig(cta_text="BÚSSOLA POLÍTICA"),
        thumbnail=BrandThumbnailConfig(),
    )


def _plan(*, intro_mode="text_only", intro_text="Intro de teste", cta_enabled=True):
    return EditorialPlan(
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand="bussola-politica",
        version=1,
        intro=Intro(mode=intro_mode, text=intro_text if intro_mode == "text_only" else None),
        source_attribution=SourceAttribution(text="Fonte original: Teste"),
        lower_thirds=[],
        context_cards=[],
        highlights=[],
        cta=Cta(enabled=cta_enabled, text="TEXTO CTA" if cta_enabled else None),
        provider="claude",
        model="claude-sonnet-5",
    )


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _fake_subprocess(monkeypatch, *, ffmpeg_returncode=0, ffmpeg_stderr="", captured_cmds=None):
    def _fake_run(cmd, capture_output=True, text=True):
        if captured_cmds is not None:
            captured_cmds.append(cmd)
        if cmd[0] == "ffprobe":
            streams = [
                {"codec_type": "video", "width": 1280, "height": 720, "r_frame_rate": "30/1"},
                {"codec_type": "audio", "sample_rate": "44100"},
            ]
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"streams": streams}))
        output_path = Path(cmd[-1])
        if ffmpeg_returncode == 0:
            output_path.write_bytes(b"fake rendered video")
        return _FakeCompletedProcess(returncode=ffmpeg_returncode, stderr=ffmpeg_stderr)

    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)


def _make_cut_file(tmp_path):
    cut_path = tmp_path / "cortes" / "008_cap08_teste.mp4"
    cut_path.parent.mkdir(parents=True, exist_ok=True)
    cut_path.write_bytes(b"fake cut bytes")
    return cut_path


def test_render_raises_when_ffmpeg_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: None)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)

    with pytest.raises(EditorialRenderError) as exc_info:
        render_editorial_video(_plan(), cut_path, _brand(tmp_path), tmp_path / "final" / "out.mp4", settings)
    assert "FFmpeg" in str(exc_info.value)


def test_render_copies_cut_directly_when_intro_and_cta_disabled(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    plan = _plan(intro_mode="disabled", cta_enabled=False)
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.intro_included is False
    assert result.cta_included is False
    assert output_path.read_bytes() == cut_path.read_bytes()
    assert not any(cmd[0] == "ffmpeg" for cmd in captured)


def test_render_skips_text_when_font_not_configured(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    result = render_editorial_video(_plan(), cut_path, _brand(tmp_path, with_font=False), output_path, settings)

    assert result.intro_included is False
    assert result.cta_included is False
    assert result.skipped_text_reason is not None
    assert "fonte" in result.skipped_text_reason.lower()
    assert output_path.exists()
    assert not any(cmd[0] == "ffmpeg" for cmd in captured)


def test_render_includes_intro_and_cta_when_font_available(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    result = render_editorial_video(_plan(), cut_path, _brand(tmp_path), output_path, settings)

    assert result.intro_included is True
    assert result.cta_included is True
    assert result.skipped_text_reason is None
    assert output_path.exists()

    ffmpeg_cmds = [cmd for cmd in captured if cmd[0] == "ffmpeg"]
    assert len(ffmpeg_cmds) == 1
    cmd = ffmpeg_cmds[0]
    assert "concat=n=3:v=1:a=1" in " ".join(cmd)
    assert "drawtext" in " ".join(cmd)
    assert "libx264" in cmd


def test_render_includes_only_intro_when_cta_disabled(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    plan = _plan(cta_enabled=False)
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.intro_included is True
    assert result.cta_included is False
    ffmpeg_cmds = [cmd for cmd in captured if cmd[0] == "ffmpeg"]
    assert "concat=n=2:v=1:a=1" in " ".join(ffmpeg_cmds[0])


def test_render_raises_on_ffmpeg_failure(tmp_path, monkeypatch):
    _fake_subprocess(monkeypatch, ffmpeg_returncode=1, ffmpeg_stderr="erro de filtro")
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    with pytest.raises(EditorialRenderError) as exc_info:
        render_editorial_video(_plan(), cut_path, _brand(tmp_path), output_path, settings)
    assert "erro de filtro" in str(exc_info.value)
