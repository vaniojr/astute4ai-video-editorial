import json
from datetime import date

from app import project as project_module
from app.brands import BrandNotFoundError
from app.config import Settings
from app.metadata import VideoMetadata
from app.project import (
    ProjectNotFoundError,
    _write_fonte_md,
    create_project,
    find_existing_project,
    load_project,
    resolve_project_dir,
    update_status,
)


def _write_brand(brands_dir, slug, *, name="Genérico"):
    brand_dir = brands_dir / slug
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "brand.toml").write_text(
        f'[brand]\nslug = "{slug}"\nname = "{name}"\n', encoding="utf-8"
    )


def _settings(tmp_path, default_brand="generic"):
    brands_dir = tmp_path / "brands"
    _write_brand(brands_dir, "generic")
    return Settings(
        projetos_dir=tmp_path / "projetos",
        whisper_model="medium",
        whisper_language="pt",
        ffmpeg_crf=18,
        ffmpeg_preset="medium",
        audio_bitrate_kbps=192,
        output_format="mp4",
        max_video_height=None,
        analysis_provider="claude",
        analysis_model="claude-sonnet-5",
        analysis_temperature=0.0,
        default_brand=default_brand,
        brands_dir=brands_dir,
        thumbnail_provider="manual",
        thumbnail_model="gpt-image-1",
        editorial_provider="claude",
        editorial_model="claude-sonnet-5",
        editorial_temperature=0.0,
        editorial_intro_seconds=10.0,
        editorial_cta_seconds=5.0,
        editorial_card_seconds=4.0,
        editorial_source_attribution_seconds=4.0,
    )


def _fake_metadata(**overrides):
    defaults = dict(
        platform="youtube",
        source_id="7xgE4ZHNWRU",
        source_url="https://www.youtube.com/watch?v=7xgE4ZHNWRU",
        title="Podcast 3 Irmãos #1033",
        channel="Podcast 3 Irmãos",
        published_at=date(2026, 8, 12),
        duration_seconds=6300,
    )
    defaults.update(overrides)
    return VideoMetadata(**defaults)


def test_create_project_builds_expected_directory_name(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    assert result.already_existed is False
    assert result.path.name == "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"
    assert result.path.parent == settings.projetos_dir


def test_create_project_creates_expected_subdirectories(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    for subdir in ("original", "audio", "cortes", "thumbs", "publicados", "logs", "analysis"):
        assert (result.path / subdir).is_dir()


def test_create_project_writes_project_json(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    data = json.loads((result.path / "project.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 2
    assert data["source_id"] == "7xgE4ZHNWRU"
    assert data["slug"] == "podcast-3-irmaos-1033"
    assert data["published_at"] == "2026-08-12"
    assert data["status"] == "created"
    assert data["brand"] == "generic"


def test_create_project_writes_fonte_md(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    content = (result.path / "01 Fonte.md").read_text(encoding="utf-8")
    assert "Podcast 3 Irmãos #1033" in content
    assert "7xgE4ZHNWRU" in content
    assert "01:45:00" in content


def test_create_project_is_idempotent_by_source_id(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    first = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)
    second = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    assert second.already_existed is True
    assert second.path == first.path
    assert second.project is None
    assert len(list(settings.projetos_dir.iterdir())) == 1


def test_create_project_falls_back_to_today_when_published_at_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        project_module, "fetch_metadata", lambda url: _fake_metadata(published_at=None)
    )

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    assert result.path.name.startswith(date.today().isoformat())


def test_write_fonte_md_does_not_overwrite_existing_file(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)
    fonte_path = result.path / "01 Fonte.md"
    fonte_path.write_text("conteúdo editado manualmente", encoding="utf-8")

    _write_fonte_md(result.project, result.path)

    assert fonte_path.read_text(encoding="utf-8") == "conteúdo editado manualmente"


def test_find_existing_project_returns_none_when_directory_absent(tmp_path):
    assert find_existing_project("abc123", tmp_path / "projetos") is None


def test_load_project_reconstructs_project(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    loaded = load_project(result.path)

    assert loaded.source_id == "7xgE4ZHNWRU"
    assert loaded.source_url == "https://www.youtube.com/watch?v=7xgE4ZHNWRU"
    assert loaded.published_at == date(2026, 8, 12)
    assert loaded.status == "created"


def test_update_status_changes_only_status_field(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    update_status(result.path, "downloaded")

    data = json.loads((result.path / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "downloaded"
    assert data["source_id"] == "7xgE4ZHNWRU"
    assert data["title"] == "Podcast 3 Irmãos #1033"


def test_resolve_project_dir_by_directory_name(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    resolved = resolve_project_dir(result.path.name, settings)

    assert resolved == result.path


def test_resolve_project_dir_by_explicit_path(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    resolved = resolve_project_dir(str(result.path), settings)

    assert resolved == result.path


def test_resolve_project_dir_raises_when_not_found(tmp_path):
    settings = _settings(tmp_path)

    try:
        resolve_project_dir("nao-existe", settings)
        assert False, "deveria ter levantado ProjectNotFoundError"
    except ProjectNotFoundError:
        pass


def test_resolve_project_dir_by_bare_source_id(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    resolved = resolve_project_dir("7xgE4ZHNWRU", settings)

    assert resolved == result.path


def test_create_project_uses_explicit_brand(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_brand(settings.brands_dir, "bussola-politica", name="Bússola Política")
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project(
        "https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings, brand="bussola-politica"
    )

    data = json.loads((result.path / "project.json").read_text(encoding="utf-8"))
    assert data["brand"] == "bussola-politica"


def test_create_project_falls_back_to_default_brand(tmp_path, monkeypatch):
    settings = _settings(tmp_path, default_brand="generic")
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    data = json.loads((result.path / "project.json").read_text(encoding="utf-8"))
    assert data["brand"] == "generic"


def test_create_project_raises_on_unknown_brand(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    try:
        create_project(
            "https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings, brand="nao-existe"
        )
        assert False, "deveria ter levantado BrandNotFoundError"
    except BrandNotFoundError:
        pass

    assert not settings.projetos_dir.exists()


def test_load_project_defaults_brand_when_missing_from_old_schema(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    result = create_project("https://www.youtube.com/watch?v=7xgE4ZHNWRU", settings)

    path = result.path / "project.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = 1
    del data["brand"]
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(result.path)

    assert loaded.brand == "generic"
