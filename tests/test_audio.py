from dataclasses import dataclass
from pathlib import Path

from app import audio as audio_module
from app.audio import AudioError, extract_audio


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _patch_which(monkeypatch, present=True):
    monkeypatch.setattr(
        audio_module.shutil, "which", lambda name: f"/usr/bin/{name}" if present else None
    )


def _patch_run(
    monkeypatch,
    *,
    ffprobe_returncode=0,
    ffprobe_stdout="audio\n",
    ffprobe_stderr="",
    ffmpeg_returncode=0,
    ffmpeg_stderr="",
):
    def _fake_run(cmd, capture_output=True, text=True):
        if cmd[0] == "ffprobe":
            return _FakeCompletedProcess(
                returncode=ffprobe_returncode, stdout=ffprobe_stdout, stderr=ffprobe_stderr
            )
        if cmd[0] == "ffmpeg":
            if ffmpeg_returncode == 0:
                Path(cmd[-1]).write_bytes(b"fake wav bytes")
            return _FakeCompletedProcess(returncode=ffmpeg_returncode, stderr=ffmpeg_stderr)
        raise AssertionError(f"comando inesperado: {cmd}")

    monkeypatch.setattr(audio_module.subprocess, "run", _fake_run)


def _make_project(tmp_path, with_video=True):
    project_dir = tmp_path / "projeto"
    original_dir = project_dir / "original"
    original_dir.mkdir(parents=True)
    if with_video:
        (original_dir / "video-original.mp4").write_bytes(b"fake video bytes")
    return project_dir


def test_extract_audio_creates_final_file(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    _patch_which(monkeypatch)
    _patch_run(monkeypatch)

    result = extract_audio(project_dir)

    assert result.skipped is False
    assert result.path.name == "audio.wav"
    assert result.path.exists()


def test_extract_audio_raises_when_video_missing(tmp_path):
    project_dir = _make_project(tmp_path, with_video=False)

    try:
        extract_audio(project_dir)
        assert False, "deveria ter levantado AudioError"
    except AudioError as exc:
        assert "download" in str(exc)


def test_extract_audio_is_idempotent_by_default(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    audio_dir = project_dir / "audio"
    audio_dir.mkdir()
    existing = audio_dir / "audio.wav"
    existing.write_bytes(b"already here")

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg/ffprobe não deveriam ser chamados")

    monkeypatch.setattr(audio_module.subprocess, "run", _fail_if_called)

    result = extract_audio(project_dir)

    assert result.skipped is True
    assert existing.read_bytes() == b"already here"


def test_extract_audio_force_reextracts(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    audio_dir = project_dir / "audio"
    audio_dir.mkdir()
    existing = audio_dir / "audio.wav"
    existing.write_bytes(b"stale content")
    _patch_which(monkeypatch)
    _patch_run(monkeypatch)

    result = extract_audio(project_dir, force=True)

    assert result.skipped is False
    assert result.path.read_bytes() == b"fake wav bytes"


def test_extract_audio_raises_when_ffmpeg_missing(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    _patch_which(monkeypatch, present=False)

    try:
        extract_audio(project_dir)
        assert False, "deveria ter levantado AudioError"
    except AudioError as exc:
        assert "FFmpeg" in str(exc)


def test_extract_audio_raises_when_no_audio_stream(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    _patch_which(monkeypatch)
    _patch_run(monkeypatch, ffprobe_stdout="")

    try:
        extract_audio(project_dir)
        assert False, "deveria ter levantado AudioError"
    except AudioError as exc:
        assert "trilha de áudio" in str(exc)


def test_extract_audio_raises_when_ffprobe_fails(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    _patch_which(monkeypatch)
    _patch_run(monkeypatch, ffprobe_returncode=1, ffprobe_stderr="arquivo corrompido")

    try:
        extract_audio(project_dir)
        assert False, "deveria ter levantado AudioError"
    except AudioError as exc:
        assert "corrompido" in str(exc)


def test_extract_audio_raises_when_ffmpeg_fails(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path)
    _patch_which(monkeypatch)
    _patch_run(monkeypatch, ffmpeg_returncode=1, ffmpeg_stderr="erro de codec")

    try:
        extract_audio(project_dir)
        assert False, "deveria ter levantado AudioError"
    except AudioError as exc:
        assert "FFmpeg" in str(exc)
