import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app import ffmpeg_utils as ffmpeg_utils_module
from app.brands import Brand, BrandAssets, BrandColors, BrandFeatures, BrandThumbnailConfig, BrandVideoConfig
from app.config import Settings
from app.editorial_models import ContextCard, Cta, EditorialPlan, Intro, SourceAttribution
from app.editorial_renderer import EditorialRenderError, _wrap_text, render_editorial_video


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
        editorial_card_seconds=4.0,
        editorial_source_attribution_seconds=4.0,
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


def _plan(
    *,
    intro_mode="text_only",
    intro_text="Intro de teste",
    cta_enabled=True,
    source_attribution_text="Fonte original: Teste",
    context_cards=None,
):
    return EditorialPlan(
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand="bussola-politica",
        version=1,
        intro=Intro(mode=intro_mode, text=intro_text if intro_mode == "text_only" else None),
        source_attribution=SourceAttribution(text=source_attribution_text),
        lower_thirds=[],
        context_cards=context_cards or [],
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


def test_render_copies_cut_directly_when_nothing_to_overlay(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    plan = _plan(intro_mode="disabled", cta_enabled=False, source_attribution_text="")
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.intro_included is False
    assert result.cta_included is False
    assert result.cards_included == 0
    assert result.source_attribution_included is False
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
    assert result.source_attribution_included is True
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


def test_render_includes_cards_as_overlay_not_extra_segment(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    cards = [
        ContextCard(kind="context", text="CONTEXTO", timestamp=5.0),
        ContextCard(kind="subtopic", text="SUBTEMA", timestamp=10.0),
    ]
    plan = _plan(intro_mode="disabled", cta_enabled=False, source_attribution_text="", context_cards=cards)
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.cards_included == 2
    ffmpeg_cmds = [cmd for cmd in captured if cmd[0] == "ffmpeg"]
    cmd_str = " ".join(ffmpeg_cmds[0])
    # Cards são overlay no próprio corte, não um segmento novo concatenado.
    assert "concat=n=1:v=1:a=1" in cmd_str
    assert cmd_str.count("drawtext") == 2
    assert "between(t,5.0,9.0)" in cmd_str
    assert "between(t,10.0,14.0)" in cmd_str


def test_render_caps_at_configured_card_duration(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    cards = [ContextCard(kind="context", text="CONTEXTO", timestamp=0.0)]
    plan = _plan(intro_mode="disabled", cta_enabled=False, source_attribution_text="", context_cards=cards)
    render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    ffmpeg_cmds = [cmd for cmd in captured if cmd[0] == "ffmpeg"]
    assert "between(t,0.0,4.0)" in " ".join(ffmpeg_cmds[0])


def test_render_includes_source_attribution_overlay(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    plan = _plan(intro_mode="disabled", cta_enabled=False, source_attribution_text="Fonte original: Teste")
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.source_attribution_included is True
    ffmpeg_cmds = [cmd for cmd in captured if cmd[0] == "ffmpeg"]
    cmd_str = " ".join(ffmpeg_cmds[0])
    assert "concat=n=1:v=1:a=1" in cmd_str
    assert "shadowcolor" in cmd_str
    assert "between(t,0,4.0)" in cmd_str


def test_render_skips_cards_and_source_attribution_without_font(tmp_path, monkeypatch):
    _fake_subprocess(monkeypatch)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    cards = [ContextCard(kind="context", text="CONTEXTO", timestamp=5.0)]
    plan = _plan(intro_mode="disabled", cta_enabled=False, context_cards=cards)
    result = render_editorial_video(plan, cut_path, _brand(tmp_path, with_font=False), output_path, settings)

    assert result.cards_included == 0
    assert result.source_attribution_included is False
    assert "cards/atribuição" in result.skipped_text_reason


def test_render_ignores_cards_with_blank_text(tmp_path, monkeypatch):
    captured = []
    _fake_subprocess(monkeypatch, captured_cmds=captured)
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    cards = [ContextCard(kind="context", text="   ", timestamp=5.0)]
    plan = _plan(intro_mode="disabled", cta_enabled=False, source_attribution_text="", context_cards=cards)
    result = render_editorial_video(plan, cut_path, _brand(tmp_path), output_path, settings)

    assert result.cards_included == 0
    assert not any(cmd[0] == "ffmpeg" for cmd in captured)


def test_render_raises_on_ffmpeg_failure(tmp_path, monkeypatch):
    _fake_subprocess(monkeypatch, ffmpeg_returncode=1, ffmpeg_stderr="erro de filtro")
    settings = _settings(tmp_path)
    cut_path = _make_cut_file(tmp_path)
    output_path = tmp_path / "final" / "out.mp4"

    with pytest.raises(EditorialRenderError) as exc_info:
        render_editorial_video(_plan(), cut_path, _brand(tmp_path), output_path, settings)
    assert "erro de filtro" in str(exc_info.value)


def test_wrap_text_preserves_explicit_line_breaks():
    # Bug real encontrado na validação manual: textwrap.wrap() sozinho
    # colapsava o \n proposital do brand.video.cta_text (ex.: "CANAL DE
    # TESTE\nCurta e compartilhe") numa linha só antes de re-quebrar.
    result = _wrap_text("CANAL DE TESTE\nCurta e compartilhe")
    assert result == "CANAL DE TESTE\nCurta e compartilhe"


def test_wrap_text_wraps_long_lines_within_each_paragraph():
    long_line = "palavra " * 20
    result = _wrap_text(f"Primeira linha curta\n{long_line}")
    lines = result.split("\n")
    assert lines[0] == "Primeira linha curta"
    assert len(lines) > 2
    assert all(len(line) <= 40 for line in lines)


def test_wrap_text_returns_original_when_empty():
    assert _wrap_text("") == ""
