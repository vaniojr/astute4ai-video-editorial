"""Teste de integração fim-a-fim do pipeline via CLI (PRD seções 34-35).

Mocka só as bordas externas (yt-dlp, ffmpeg/ffprobe, faster-whisper) e
verifica que project.json.status avança corretamente por todos os
estágios, com cada comando encontrando os artefatos do comando anterior.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from typer.testing import CliRunner

from app import transcriber as transcriber_module
from cli.main import app

runner = CliRunner()

_CSV_CONTENT = (
    "Ordem Publicacao,Prioridade,Capitulo,Bloco Editorial,Acao Editorial,"
    "Timestamp Inicial,Timestamp Final,Duracao,Tema Principal,Titulo Sugerido,"
    "Palavra-chave Principal,Trecho para Validar Primeiro,Resumo,"
    "Pergunta Principal,Independente,Precisa Contexto Anterior,Grau de Confianca,"
    "Observacoes\n"
    "1,A,01,Bloco 1,Manter,00:00:02,00:00:08,,Tema,Titulo do corte,palavra,,"
    "Resumo,,Sim,Nao,Alto,\n"
)


class _FakeYoutubeDL:
    def __init__(self, opts):
        self._opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=False):
        info = {
            "id": "jNQXAC9IVRw",
            "title": "Me at the zoo",
            "channel": "jawed",
            "upload_date": "20050424",
            "duration": 19,
        }
        if download:
            final_path = Path(self._opts["outtmpl"].replace("%(ext)s", "mp4"))
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_bytes(b"fake video bytes")
        return info


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _fake_subprocess_run(cmd, capture_output=True, text=True):
    if cmd[0] == "ffprobe":
        if "format=duration" in cmd:
            return _FakeCompletedProcess(returncode=0, stdout="19.0")
        return _FakeCompletedProcess(returncode=0, stdout="audio\n")
    if cmd[0] == "ffmpeg":
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake media bytes")
        return _FakeCompletedProcess(returncode=0)
    raise AssertionError(f"comando inesperado: {cmd}")


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperInfo:
    def __init__(self, language):
        self.language = language


def _make_fake_whisper_model():
    class _FakeWhisperModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            pass

        def transcribe(self, audio_path, language=None):
            segments = [_FakeSegment(0.0, 5.0, "Ola mundo")]
            return iter(segments), _FakeWhisperInfo(language=language or "pt")

    return _FakeWhisperModel


def _status(project_dir: Path) -> str:
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    return data["status"]


def test_full_pipeline_advances_status_through_all_stages(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _FakeYoutubeDL(opts))
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(transcriber_module, "WhisperModel", _make_fake_whisper_model())

    init_result = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=jNQXAC9IVRw"])
    assert init_result.exit_code == 0, init_result.stdout

    project_dir = tmp_path / "projetos" / "2005-04-24_me-at-the-zoo_jNQXAC9IVRw"
    assert project_dir.is_dir()
    assert _status(project_dir) == "created"

    download_result = runner.invoke(app, ["download", str(project_dir)])
    assert download_result.exit_code == 0, download_result.stdout
    assert (project_dir / "original" / "video-original.mp4").exists()
    assert _status(project_dir) == "downloaded"

    audio_result = runner.invoke(app, ["audio", str(project_dir)])
    assert audio_result.exit_code == 0, audio_result.stdout
    assert (project_dir / "audio" / "audio.wav").exists()
    assert _status(project_dir) == "audio_ready"

    transcribe_result = runner.invoke(app, ["transcribe", str(project_dir)])
    assert transcribe_result.exit_code == 0, transcribe_result.stdout
    assert (project_dir / "02 Transcricao.md").exists()
    assert _status(project_dir) == "transcribed"

    (project_dir / "03 Analise.csv").write_text(_CSV_CONTENT, encoding="utf-8")

    dry_run_result = runner.invoke(app, ["cut", str(project_dir), "--dry-run"])
    assert dry_run_result.exit_code == 0, dry_run_result.stdout
    assert "Cortes elegíveis:" in dry_run_result.stdout
    assert _status(project_dir) == "analyzed"

    cut_result = runner.invoke(app, ["cut", str(project_dir)])
    assert cut_result.exit_code == 0, cut_result.stdout
    cortes = list((project_dir / "cortes").glob("*.mp4"))
    assert len(cortes) == 1
    assert _status(project_dir) == "cut"

    status_result = runner.invoke(app, ["status", str(project_dir)])
    assert status_result.exit_code == 0, status_result.stdout
    assert "Status: cut" in status_result.stdout
    assert "presente" in status_result.stdout


def test_status_resolves_project_by_bare_source_id(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _FakeYoutubeDL(opts))

    runner.invoke(app, ["init", "https://www.youtube.com/watch?v=jNQXAC9IVRw"])

    result = runner.invoke(app, ["status", "jNQXAC9IVRw"])

    assert result.exit_code == 0, result.stdout
    assert "Me at the zoo" in result.stdout
