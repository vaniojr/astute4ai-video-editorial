from datetime import date

from typer.testing import CliRunner

from app import project as project_module
from app.metadata import MetadataError, VideoMetadata
from cli.main import app

runner = CliRunner()


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


def test_init_creates_project(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])

    assert result.exit_code == 0
    project_dir = tmp_path / "projetos" / "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"
    assert project_dir.is_dir()
    assert (project_dir / "project.json").is_file()
    assert (project_dir / "01 Fonte.md").is_file()
    assert "Projeto criado" in result.stdout


def test_init_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])
    second = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])

    assert second.exit_code == 0
    assert "Projeto já existente" in second.stdout


def test_init_reports_metadata_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    def _raise(url):
        raise MetadataError("mensagem acionável")

    monkeypatch.setattr(project_module, "fetch_metadata", _raise)

    result = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=invalid"])

    assert result.exit_code == 1
