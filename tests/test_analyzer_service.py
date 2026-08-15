"""Testes de app/analyzer.py — provider sempre mockado (nunca chama a API real)."""

import json
from dataclasses import dataclass

import pytest

import app.analysis as analysis_module
import app.analyzer as analyzer_module
from app.analyzer import (
    AnalysisProvider,
    AnalysisRequest,
    AnalysisResult,
    AnalysisServiceError,
    ChapterCandidate,
    analyze_project,
    plan_analysis,
)
from app.config import Settings


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
    )


def _make_project(tmp_path, *, with_video=True, transcript_text="conteudo da transcricao"):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir(parents=True)
    (project_dir / "01 Fonte.md").write_text(
        "# Fonte\n\nTitulo original:\nVideo de teste\n", encoding="utf-8"
    )
    (project_dir / "02 Transcricao.md").write_text(transcript_text, encoding="utf-8")

    project_json = {
        "schema_version": 1,
        "platform": "youtube",
        "source_id": "abc123",
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "title": "Video de teste",
        "channel": "Canal Teste",
        "published_at": "2026-01-01",
        "duration_seconds": 6303,
        "slug": "video-de-teste",
        "created_at": "2026-01-01T10:00:00-03:00",
        "status": "transcribed",
    }
    (project_dir / "project.json").write_text(json.dumps(project_json), encoding="utf-8")

    if with_video:
        (project_dir / "original").mkdir(parents=True)
        (project_dir / "original" / "video-original.mp4").write_bytes(b"fake video")

    return project_dir


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _fake_ffprobe(monkeypatch, duration_seconds=6303.0):
    def _fake_run(cmd, capture_output=True, text=True):
        return _FakeCompletedProcess(returncode=0, stdout=str(duration_seconds))

    monkeypatch.setattr(analysis_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(analysis_module.shutil, "which", lambda name: f"/usr/bin/{name}")


class _FakeProvider(AnalysisProvider):
    def __init__(self, chapters, usage=None, captured=None):
        self._chapters = chapters
        self._usage = usage
        self._captured = captured

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        if self._captured is not None:
            self._captured.append(request)
        return AnalysisResult(
            chapters=self._chapters, provider="claude", model="claude-sonnet-5", usage=self._usage
        )


def _chapter(**overrides):
    base = dict(
        prioridade="A",
        capitulo=1,
        bloco_editorial="Bloco 1",
        acao_editorial="Manter",
        timestamp_inicial="00:00:05",
        timestamp_final="00:00:15",
        tema_principal="Tema",
        titulo_sugerido="Titulo",
        palavra_chave_principal="palavra",
        trecho_para_validar_primeiro="",
        resumo="Resumo",
        pergunta_principal="",
        independente="Sim",
        precisa_contexto_anterior="Nao",
        grau_de_confianca="Alto",
        observacoes="",
    )
    base.update(overrides)
    return ChapterCandidate(**base)


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(analyzer_module, "get_analysis_provider", lambda name, **kwargs: provider)


def test_plan_analysis_raises_when_source_missing(tmp_path):
    settings = _settings(tmp_path)
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()
    (project_dir / "02 Transcricao.md").write_text("x", encoding="utf-8")

    with pytest.raises(AnalysisServiceError):
        plan_analysis(project_dir, settings)


def test_plan_analysis_raises_when_transcript_missing(tmp_path):
    settings = _settings(tmp_path)
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()
    (project_dir / "01 Fonte.md").write_text("x", encoding="utf-8")

    with pytest.raises(AnalysisServiceError):
        plan_analysis(project_dir, settings)


def test_plan_analysis_reports_char_count_and_defaults(tmp_path):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path, transcript_text="0123456789")

    plan = plan_analysis(project_dir, settings)

    assert plan.transcript_char_count == 10
    assert plan.provider == "claude"
    assert plan.model == "claude-sonnet-5"
    assert plan.already_exists is False
    assert plan.long_transcript_warning is None


def test_plan_analysis_warns_on_long_transcript(tmp_path):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path, transcript_text="x" * 200_000)

    plan = plan_analysis(project_dir, settings)

    assert plan.long_transcript_warning is not None


def test_plan_analysis_detects_existing_csv(tmp_path):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    (project_dir / "03 Analise.csv").write_text("x", encoding="utf-8")

    plan = plan_analysis(project_dir, settings)

    assert plan.already_exists is True


def test_analyze_project_writes_csv_and_advances_status(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_provider(monkeypatch, _FakeProvider([_chapter()]))

    result = analyze_project(project_dir, settings)

    assert result.skipped is False
    csv_path = project_dir / "03 Analise.csv"
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8-sig")
    assert "Titulo" in content
    assert "00:00:05" in content

    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "analyzed"


def test_analyze_project_computes_duration_deterministically(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch, duration_seconds=6303.0)
    _patch_provider(
        monkeypatch,
        _FakeProvider([_chapter(timestamp_inicial="00:00:05", timestamp_final="00:00:15")]),
    )

    result = analyze_project(project_dir, settings)

    assert result.dry_run_report is not None
    chapter = result.dry_run_report.chapters[0]
    assert chapter.row.duracao == "00:00:10"


def test_analyze_project_renumbers_chapters_by_start_time(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    chapters = [
        _chapter(capitulo=5, timestamp_inicial="00:01:00", timestamp_final="00:01:10"),
        _chapter(capitulo=1, timestamp_inicial="00:00:05", timestamp_final="00:00:15"),
    ]
    _patch_provider(monkeypatch, _FakeProvider(chapters))

    result = analyze_project(project_dir, settings)

    ordered = result.dry_run_report.chapters
    assert ordered[0].row.timestamp_inicial == "00:00:05"
    assert ordered[0].row.ordem_publicacao == "1"
    assert ordered[0].row.capitulo == "1"
    assert ordered[1].row.ordem_publicacao == "2"
    assert ordered[1].row.capitulo == "2"


def test_analyze_project_is_idempotent_by_default(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    (project_dir / "03 Analise.csv").write_text("existente", encoding="utf-8")
    captured = []
    _patch_provider(monkeypatch, _FakeProvider([_chapter()], captured=captured))

    result = analyze_project(project_dir, settings)

    assert result.skipped is True
    assert captured == []
    assert (project_dir / "03 Analise.csv").read_text(encoding="utf-8") == "existente"


def test_analyze_project_force_regenerates(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    (project_dir / "03 Analise.csv").write_text("antigo", encoding="utf-8")
    _fake_ffprobe(monkeypatch)
    _patch_provider(monkeypatch, _FakeProvider([_chapter()]))

    result = analyze_project(project_dir, settings, force=True)

    assert result.skipped is False
    content = (project_dir / "03 Analise.csv").read_text(encoding="utf-8-sig")
    assert "antigo" not in content


def test_analyze_project_raises_when_provider_returns_no_chapters(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)
    _patch_provider(monkeypatch, _FakeProvider([]))

    with pytest.raises(AnalysisServiceError):
        analyze_project(project_dir, settings)


def test_analyze_project_status_not_advanced_when_provider_fails(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir = _make_project(tmp_path)

    class _FailingProvider(AnalysisProvider):
        def analyze(self, request):
            raise AnalysisServiceError("falha simulada")

    _patch_provider(monkeypatch, _FailingProvider())

    with pytest.raises(AnalysisServiceError):
        analyze_project(project_dir, settings)

    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "transcribed"
