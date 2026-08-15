import json
from datetime import date

from typer.testing import CliRunner

from app import project as project_module
from app.audio import AudioError, AudioResult
from app.downloader import DownloadError, DownloadResult
from app.metadata import MetadataError, VideoMetadata
from app.transcriber import TranscribeResult, TranscriptionError
from cli import main as cli_main
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


def _create_project(tmp_path, monkeypatch):
    projetos_dir = tmp_path / "projetos"
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(projetos_dir))
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])
    return projetos_dir / "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"


def test_download_creates_file_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_download(pdir, url, settings, force=False):
        final = pdir / "original" / "video-original.mp4"
        final.write_bytes(b"fake video bytes")
        return DownloadResult(path=final, skipped=False)

    monkeypatch.setattr(cli_main, "download_video", _fake_download)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 0
    assert "Download concluído" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "downloaded"


def test_download_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_download(pdir, url, settings, force=False):
        final = pdir / "original" / "video-original.mp4"
        return DownloadResult(path=final, skipped=True)

    monkeypatch.setattr(cli_main, "download_video", _fake_download)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 0
    assert "Arquivo original já existe." in result.stdout
    assert "Nenhum download realizado." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_download_reports_download_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, url, settings, force=False):
        raise DownloadError("mensagem acionável")

    monkeypatch.setattr(cli_main, "download_video", _raise)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 1


def test_download_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["download", "nao-existe"])

    assert result.exit_code == 1


def test_audio_creates_file_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_extract(pdir, force=False):
        final = pdir / "audio" / "audio.wav"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"fake wav bytes")
        return AudioResult(path=final, skipped=False)

    monkeypatch.setattr(cli_main, "extract_audio", _fake_extract)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 0
    assert "Áudio extraído" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "audio_ready"


def test_audio_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_extract(pdir, force=False):
        final = pdir / "audio" / "audio.wav"
        return AudioResult(path=final, skipped=True)

    monkeypatch.setattr(cli_main, "extract_audio", _fake_extract)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 0
    assert "Arquivo de áudio já existe." in result.stdout
    assert "Nenhuma extração realizada." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_audio_reports_extraction_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, force=False):
        raise AudioError("mensagem acionável")

    monkeypatch.setattr(cli_main, "extract_audio", _raise)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 1


def test_audio_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["audio", "nao-existe"])

    assert result.exit_code == 1


def test_transcribe_creates_files_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_transcribe(pdir, settings, force=False):
        md_path = pdir / "02 Transcricao.md"
        json_path = pdir / "transcricao.json"
        md_path.write_text("# Transcrição", encoding="utf-8")
        json_path.write_text("{}", encoding="utf-8")
        return TranscribeResult(md_path=md_path, json_path=json_path, skipped=False)

    monkeypatch.setattr(cli_main, "transcribe_project", _fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 0
    assert "Transcrição concluída" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "transcribed"


def test_transcribe_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_transcribe(pdir, settings, force=False):
        return TranscribeResult(
            md_path=pdir / "02 Transcricao.md", json_path=pdir / "transcricao.json", skipped=True
        )

    monkeypatch.setattr(cli_main, "transcribe_project", _fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 0
    assert "Transcrição já existe." in result.stdout
    assert "Nenhuma transcrição realizada." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_transcribe_reports_transcription_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, settings, force=False):
        raise TranscriptionError("mensagem acionável")

    monkeypatch.setattr(cli_main, "transcribe_project", _raise)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 1


def test_transcribe_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["transcribe", "nao-existe"])

    assert result.exit_code == 1
