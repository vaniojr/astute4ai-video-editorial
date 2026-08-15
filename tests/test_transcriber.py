import json
from dataclasses import dataclass
from pathlib import Path

from app import transcriber as transcriber_module
from app.config import Settings
from app.transcriber import FasterWhisperProvider, TranscriptionError, transcribe_project


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str


@dataclass
class _FakeInfo:
    language: str


def _make_fake_whisper_model(segments, result_language="en", raise_error=None):
    class _FakeWhisperModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            self.model_size = model_size

        def transcribe(self, audio_path, language=None):
            if raise_error is not None:
                raise raise_error
            return iter(segments), _FakeInfo(language=result_language)

    return _FakeWhisperModel


def _settings(tmp_path, whisper_model="tiny", whisper_language="en"):
    return Settings(
        projetos_dir=tmp_path / "projetos",
        whisper_model=whisper_model,
        whisper_language=whisper_language,
        ffmpeg_crf=18,
        ffmpeg_preset="medium",
        audio_bitrate_kbps=192,
        output_format="mp4",
        max_video_height=None,
        analysis_provider="claude",
        analysis_model="claude-sonnet-5",
        analysis_temperature=0.0,
    )


def _make_project_with_audio(tmp_path, with_audio=True):
    project_dir = tmp_path / "projeto"
    audio_dir = project_dir / "audio"
    audio_dir.mkdir(parents=True)
    if with_audio:
        (audio_dir / "audio.wav").write_bytes(b"fake wav bytes")
    return project_dir


def test_faster_whisper_provider_maps_segments(monkeypatch):
    segments = [
        _FakeSegment(start=0.0, end=4.2, text=" Hello world "),
        _FakeSegment(start=4.2, end=9.0, text="Second segment"),
    ]
    monkeypatch.setattr(
        transcriber_module, "WhisperModel", _make_fake_whisper_model(segments, result_language="en")
    )

    provider = FasterWhisperProvider(model_size="tiny", language="en")
    result = provider.transcribe(Path("/fake/audio.wav"))

    assert result.language == "en"
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert result.segments[0].start_seconds == 0.0
    assert result.segments[1].index == 1


def test_faster_whisper_provider_wraps_errors(monkeypatch):
    monkeypatch.setattr(
        transcriber_module,
        "WhisperModel",
        _make_fake_whisper_model([], raise_error=RuntimeError("boom")),
    )

    provider = FasterWhisperProvider(model_size="tiny", language="en")
    try:
        provider.transcribe(Path("/fake/audio.wav"))
        assert False, "deveria ter levantado TranscriptionError"
    except TranscriptionError:
        pass


def test_transcribe_project_creates_md_and_json(tmp_path, monkeypatch):
    project_dir = _make_project_with_audio(tmp_path)
    settings = _settings(tmp_path)
    segments = [
        _FakeSegment(start=0.0, end=4.2, text="Hello world"),
        _FakeSegment(start=4.2, end=9.0, text="Second segment"),
    ]
    monkeypatch.setattr(
        transcriber_module, "WhisperModel", _make_fake_whisper_model(segments, result_language="en")
    )

    result = transcribe_project(project_dir, settings)

    assert result.skipped is False
    assert result.md_path.exists()
    assert result.json_path.exists()
    md_content = result.md_path.read_text(encoding="utf-8")
    assert "[00:00:00 → 00:00:04]" in md_content
    assert "Hello world" in md_content
    json_data = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert json_data["language"] == "en"
    assert len(json_data["segments"]) == 2
    assert json_data["segments"][0]["text"] == "Hello world"


def test_transcribe_project_raises_when_audio_missing(tmp_path):
    project_dir = _make_project_with_audio(tmp_path, with_audio=False)
    settings = _settings(tmp_path)

    try:
        transcribe_project(project_dir, settings)
        assert False, "deveria ter levantado TranscriptionError"
    except TranscriptionError as exc:
        assert "áudio" in str(exc).lower()


def test_transcribe_project_is_idempotent_by_default(tmp_path, monkeypatch):
    project_dir = _make_project_with_audio(tmp_path)
    settings = _settings(tmp_path)
    md_path = project_dir / "02 Transcricao.md"
    md_path.write_text("conteúdo existente", encoding="utf-8")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("WhisperModel não deveria ser instanciado")

    monkeypatch.setattr(transcriber_module, "WhisperModel", _fail_if_called)

    result = transcribe_project(project_dir, settings)

    assert result.skipped is True
    assert md_path.read_text(encoding="utf-8") == "conteúdo existente"


def test_transcribe_project_force_retranscribes(tmp_path, monkeypatch):
    project_dir = _make_project_with_audio(tmp_path)
    settings = _settings(tmp_path)
    md_path = project_dir / "02 Transcricao.md"
    md_path.write_text("conteúdo antigo", encoding="utf-8")
    segments = [_FakeSegment(start=0.0, end=1.0, text="Novo conteúdo")]
    monkeypatch.setattr(
        transcriber_module, "WhisperModel", _make_fake_whisper_model(segments, result_language="pt")
    )

    result = transcribe_project(project_dir, settings, force=True)

    assert result.skipped is False
    assert "Novo conteúdo" in md_path.read_text(encoding="utf-8")


def test_transcribe_project_wraps_provider_errors(tmp_path, monkeypatch):
    project_dir = _make_project_with_audio(tmp_path)
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        transcriber_module,
        "WhisperModel",
        _make_fake_whisper_model([], raise_error=RuntimeError("boom")),
    )

    try:
        transcribe_project(project_dir, settings)
        assert False, "deveria ter levantado TranscriptionError"
    except TranscriptionError:
        pass
