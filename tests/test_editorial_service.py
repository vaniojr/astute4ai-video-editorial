import json
from dataclasses import dataclass

import pytest

from app import editorial_service as editorial_service_module
from app import ffmpeg_utils as ffmpeg_utils_module
from app.analysis import AnalysisError, AnalysisRow, write_analysis_csv
from app.config import Settings
from app.editorial_provider import (
    EditorialCandidate,
    EditorialProvider,
    EditorialResult,
    RawContextCard,
    RawHighlight,
)
from app.editorial_service import EditorialServiceError, generate_editorial, plan_editorial


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
    )


def _write_generic_brand(brands_dir, *, cta_enabled=False):
    brand_dir = brands_dir / "generic"
    brand_dir.mkdir(parents=True)
    features = f"cta_enabled = {'true' if cta_enabled else 'false'}"
    video = 'cta_text = "TEXTO CTA GENERICO"\n' if cta_enabled else ""
    (brand_dir / "brand.toml").write_text(
        f'[brand]\nslug = "generic"\nname = "Genérico"\n\n[features]\n{features}\n\n[video]\n{video}',
        encoding="utf-8",
    )


def _make_project(tmp_path, *, with_cut_file=True, with_transcript=True):
    project_dir = tmp_path / "projeto"
    (project_dir / "original").mkdir(parents=True)
    (project_dir / "original" / "video-original.mp4").write_bytes(b"fake video")
    (project_dir / "cortes").mkdir(parents=True)

    project_json = {
        "schema_version": 2,
        "platform": "youtube",
        "source_id": "abc123",
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "title": "Podcast de Teste",
        "channel": "Canal Teste",
        "published_at": "2026-01-01",
        "duration_seconds": 6303,
        "slug": "podcast-de-teste",
        "created_at": "2026-01-01T10:00:00-03:00",
        "status": "cut",
        "brand": "generic",
    }
    (project_dir / "project.json").write_text(json.dumps(project_json), encoding="utf-8")

    write_analysis_csv(
        project_dir / "03 Analise.csv",
        [
            AnalysisRow(
                ordem_publicacao="8",
                capitulo="8",
                acao_editorial="Manter",
                timestamp_inicial="00:00:10",
                timestamp_final="00:00:20",
                tema_principal="Governabilidade",
                titulo_sugerido="Nao vou ser usado pelo Centrao",
            )
        ],
    )

    if with_cut_file:
        (project_dir / "cortes" / "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4").write_bytes(b"fake cut")

    if with_transcript:
        (project_dir / "transcricao.json").write_text(
            json.dumps(
                {
                    "language": "pt",
                    "segments": [
                        {"index": 0, "start": 10.0, "end": 15.0, "text": "primeira parte do corte"},
                        {"index": 1, "start": 15.0, "end": 20.0, "text": "segunda parte do corte"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    return project_dir


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _fake_ffprobe(monkeypatch, duration_seconds=6303.0):
    def _fake_run(cmd, capture_output=True, text=True):
        return _FakeCompletedProcess(returncode=0, stdout=str(duration_seconds))

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")


class _FakeEditorialProvider(EditorialProvider):
    def __init__(self, candidate=None, captured=None):
        self._candidate = candidate or EditorialCandidate(
            intro_text="Intro gerada",
            context_cards=[RawContextCard(kind="context", text="CONTEXTO", position_fraction=0.5)],
            highlights=[RawHighlight(quote="primeira parte")],
        )
        self._captured = captured

    def plan(self, request):
        if self._captured is not None:
            self._captured.append(request)
        return EditorialResult(candidate=self._candidate, provider="claude", model="claude-sonnet-5")


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(editorial_service_module, "get_editorial_provider", lambda name, **kwargs: provider)


def test_plan_editorial_raises_when_chapter_not_found(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(AnalysisError):
        plan_editorial(project_dir, settings, chapter=99)


def test_plan_editorial_raises_when_cut_file_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path, with_cut_file=False)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(EditorialServiceError):
        plan_editorial(project_dir, settings, chapter=8)


def test_plan_editorial_raises_when_transcript_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path, with_transcript=False)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(EditorialServiceError):
        plan_editorial(project_dir, settings, chapter=8)


def test_plan_editorial_does_not_require_api_key(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    plan = plan_editorial(project_dir, settings, chapter=8)

    assert plan.provider == "claude"
    assert plan.already_exists is False
    assert plan.existing_plan_versions == 0
    assert "primeira parte do corte" in plan.transcript_excerpt


def test_generate_editorial_writes_versioned_plan_and_metadata(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir, cta_enabled=True)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_provider(monkeypatch, _FakeEditorialProvider())

    result = generate_editorial(project_dir, settings, chapter=8)

    assert result.skipped is False
    assert result.plan_path.name == "editorial_plan_v001.json"
    assert result.metadata_path.exists()

    plan_data = json.loads(result.plan_path.read_text(encoding="utf-8"))
    assert plan_data["intro"]["text"] == "Intro gerada"
    assert plan_data["context_cards"][0]["timestamp"] == 5.0
    assert plan_data["highlights"][0]["text"] == "primeira parte"
    assert plan_data["highlights"][0]["start"] == 0.0
    assert plan_data["cta"]["enabled"] is True

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "planned"
    assert metadata["latest_plan"] == "editorial_plan_v001.json"

    log_path = project_dir / "logs" / "pipeline.log"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]


def test_generate_editorial_is_idempotent_by_default(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_provider(monkeypatch, _FakeEditorialProvider())

    first = generate_editorial(project_dir, settings, chapter=8)
    second = generate_editorial(project_dir, settings, chapter=8)

    assert first.skipped is False
    assert second.skipped is True


def test_generate_editorial_force_creates_new_version(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_provider(monkeypatch, _FakeEditorialProvider())

    first = generate_editorial(project_dir, settings, chapter=8)
    second = generate_editorial(project_dir, settings, chapter=8, force=True)

    assert first.plan_path.name == "editorial_plan_v001.json"
    assert second.plan_path.name == "editorial_plan_v002.json"
    assert first.plan_path.exists()
    assert second.plan_path.exists()


def test_generate_editorial_sends_only_cut_excerpt_not_full_transcript(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    (project_dir / "transcricao.json").write_text(
        json.dumps(
            {
                "language": "pt",
                "segments": [
                    {"index": 0, "start": 0.0, "end": 5.0, "text": "conteudo bem antes do corte"},
                    {"index": 1, "start": 10.0, "end": 15.0, "text": "primeira parte do corte"},
                    {"index": 2, "start": 15.0, "end": 20.0, "text": "segunda parte do corte"},
                    {"index": 3, "start": 5000.0, "end": 5005.0, "text": "conteudo bem depois do corte"},
                ],
            }
        ),
        encoding="utf-8",
    )
    _fake_ffprobe(monkeypatch)
    captured = []
    _patch_provider(monkeypatch, _FakeEditorialProvider(captured=captured))

    generate_editorial(project_dir, settings, chapter=8)

    assert len(captured) == 1
    assert "conteudo bem antes do corte" not in captured[0].transcript_excerpt
    assert "conteudo bem depois do corte" not in captured[0].transcript_excerpt
    assert "primeira parte do corte" in captured[0].transcript_excerpt
