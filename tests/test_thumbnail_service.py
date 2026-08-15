import json
from dataclasses import dataclass

import pytest

from app import ffmpeg_utils as ffmpeg_utils_module
from app import thumbnail_service as thumbnail_service_module
from app.analysis import AnalysisError, AnalysisRow, write_analysis_csv
from app.config import Settings
from app.thumbnail_frames import ThumbnailFramesError
from app.thumbnail_provider import ThumbnailImageResult, ThumbnailProvider, ThumbnailResult
from app.thumbnail_service import (
    ThumbnailServiceError,
    generate_thumbnail,
    plan_thumbnail,
    select_thumbnail_version,
)


def _settings(tmp_path, thumbnail_provider="manual"):
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
        thumbnail_provider=thumbnail_provider,
        thumbnail_model="gpt-image-1",
        editorial_provider="claude",
        editorial_model="claude-sonnet-5",
        editorial_temperature=0.0,
        editorial_intro_seconds=10.0,
        editorial_cta_seconds=5.0,
        editorial_card_seconds=4.0,
        editorial_source_attribution_seconds=4.0,
    )


def _write_generic_brand(brands_dir):
    brand_dir = brands_dir / "generic"
    brand_dir.mkdir(parents=True)
    (brand_dir / "brand.toml").write_text(
        '[brand]\nslug = "generic"\nname = "Genérico"\n', encoding="utf-8"
    )


def _make_project(tmp_path, *, with_cut_file=True):
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
                timestamp_inicial="00:29:07",
                timestamp_final="00:37:22",
                tema_principal="Governabilidade",
                titulo_sugerido="Nao vou ser usado pelo Centrao",
                pergunta_principal="Como formar maioria?",
            )
        ],
    )

    if with_cut_file:
        (project_dir / "cortes" / "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4").write_bytes(b"fake cut")

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


def _patch_extract_frames(monkeypatch, frame_count=9):
    def _fake_extract(cut_path, output_dir, duration_seconds, *, count=9):
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(1, frame_count + 1):
            p = output_dir / f"frame-{i:02d}.jpg"
            p.write_bytes(b"fake jpeg")
            paths.append(p)
        return paths

    monkeypatch.setattr(thumbnail_service_module, "extract_frames", _fake_extract)


class _FakeImageProvider(ThumbnailProvider):
    def __init__(self, image_count=2):
        self._image_count = image_count

    def generate(self, request):
        images = [ThumbnailImageResult(content=b"fake png bytes") for _ in range(self._image_count)]
        return ThumbnailResult(images=images, provider="fake")


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        thumbnail_service_module, "get_thumbnail_provider", lambda name, model=None: provider
    )


def test_plan_thumbnail_raises_when_provider_unsupported(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(ThumbnailServiceError):
        plan_thumbnail(project_dir, settings, chapter=8, provider="outro")


def test_plan_thumbnail_raises_when_chapter_not_found(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(AnalysisError):
        plan_thumbnail(project_dir, settings, chapter=99)


def test_plan_thumbnail_raises_when_cut_file_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path, with_cut_file=False)
    _fake_ffprobe(monkeypatch)

    with pytest.raises(ThumbnailServiceError) as exc_info:
        plan_thumbnail(project_dir, settings, chapter=8)
    assert "cut" in str(exc_info.value).lower() or "corte" in str(exc_info.value).lower()


def test_plan_thumbnail_succeeds_with_valid_chapter(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)

    plan = plan_thumbnail(project_dir, settings, chapter=8)

    assert plan.provider == "manual"
    assert plan.already_exists is False
    assert plan.existing_image_versions == 0
    assert plan.cut_path.name == "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4"
    assert plan.thumb_dir.name == "008_cap08_nao-vou-ser-usado-pelo-centrao"
    assert plan.brand.slug == "generic"


def test_generate_thumbnail_writes_expected_artifacts(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)

    result = generate_thumbnail(project_dir, settings, chapter=8)

    assert result.skipped is False
    assert len(result.frame_paths) == 9
    assert result.briefing_path.exists()
    assert result.metadata_path.exists()
    assert result.image_paths == []

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["chapter"] == "8"
    assert metadata["provider"] == "manual"
    assert metadata["participants_unknown"] is True
    assert metadata["status"] == "briefing_ready"
    assert len(metadata["frames"]) == 9
    assert metadata["headline"] == "Nao vou ser usado pelo Centrao"
    assert metadata["headline_options"] == ["Nao vou ser usado pelo Centrao", "Como formar maioria?", "Governabilidade"]
    assert metadata["images"] == []
    assert metadata["selected"] is None

    log_path = project_dir / "logs" / "pipeline.log"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]


def test_generate_thumbnail_is_idempotent_by_default(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)

    first = generate_thumbnail(project_dir, settings, chapter=8)
    second = generate_thumbnail(project_dir, settings, chapter=8)

    assert first.skipped is False
    assert second.skipped is True


def test_generate_thumbnail_force_regenerates(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)

    generate_thumbnail(project_dir, settings, chapter=8)
    second = generate_thumbnail(project_dir, settings, chapter=8, force=True)

    assert second.skipped is False


def test_generate_thumbnail_propagates_ffmpeg_failure(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)

    def _fail_extract(cut_path, output_dir, duration_seconds, *, count=9):
        raise ThumbnailFramesError("ffmpeg falhou")

    monkeypatch.setattr(thumbnail_service_module, "extract_frames", _fail_extract)

    with pytest.raises(ThumbnailFramesError):
        generate_thumbnail(project_dir, settings, chapter=8)

    log_path = project_dir / "logs" / "pipeline.log"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    assert [e["resultado"] for e in entries] == ["iniciado", "erro"]


def test_generate_thumbnail_writes_versioned_images_from_provider(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)
    _patch_provider(monkeypatch, _FakeImageProvider(image_count=2))

    result = generate_thumbnail(project_dir, settings, chapter=8)

    assert [p.name for p in result.image_paths] == ["thumbnail_v001.png", "thumbnail_v002.png"]
    for path in result.image_paths:
        assert path.read_bytes() == b"fake png bytes"

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "generated"
    assert metadata["images"] == ["thumbnail_v001.png", "thumbnail_v002.png"]


def test_generate_thumbnail_force_adds_new_versions_without_overwriting(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)
    _patch_provider(monkeypatch, _FakeImageProvider(image_count=1))

    first = generate_thumbnail(project_dir, settings, chapter=8)
    second = generate_thumbnail(project_dir, settings, chapter=8, force=True)

    assert [p.name for p in first.image_paths] == ["thumbnail_v001.png"]
    assert [p.name for p in second.image_paths] == ["thumbnail_v002.png"]
    assert first.image_paths[0].exists()
    assert second.image_paths[0].exists()


def test_select_thumbnail_version_copies_and_updates_metadata(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)
    _patch_provider(monkeypatch, _FakeImageProvider(image_count=2))

    generate_thumbnail(project_dir, settings, chapter=8)
    result = select_thumbnail_version(project_dir, settings, chapter=8, version=2)

    assert result.selected_path.name == "selected.png"
    assert result.selected_path.read_bytes() == b"fake png bytes"

    metadata = json.loads((result.thumb_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["selected"] == "thumbnail_v002.png"
    assert metadata["status"] == "selected"


def test_select_thumbnail_version_raises_when_version_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_generic_brand(settings.brands_dir)
    project_dir = _make_project(tmp_path)
    _fake_ffprobe(monkeypatch)
    _patch_extract_frames(monkeypatch)

    generate_thumbnail(project_dir, settings, chapter=8)

    with pytest.raises(ThumbnailServiceError):
        select_thumbnail_version(project_dir, settings, chapter=8, version=1)
