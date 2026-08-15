"""Transcrição do áudio com timestamps preservados (PRD seção 13).

`TranscriptionProvider` é a interface plugável pedida pelo PRD; hoje só
existe `FasterWhisperProvider`, mas a interface já permite trocar de motor
(ex.: `OpenAIProvider`, `ExternalProvider`) sem alterar `transcribe_project`.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List

from faster_whisper import WhisperModel

from app.config import Settings

_MD_FILENAME = "02 Transcricao.md"
_JSON_FILENAME = "transcricao.json"


class TranscriptionError(Exception):
    """Erro acionável ao transcrever o áudio."""


@dataclass(frozen=True)
class TranscriptSegment:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    segments: List[TranscriptSegment]


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult: ...


class FasterWhisperProvider(TranscriptionProvider):
    def __init__(self, model_size: str, language: str):
        self._model_size = model_size
        self._language = language

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        try:
            model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
            segments_iter, info = model.transcribe(str(audio_path), language=self._language)
            segments = [
                TranscriptSegment(
                    index=i,
                    start_seconds=segment.start,
                    end_seconds=segment.end,
                    text=segment.text.strip(),
                )
                for i, segment in enumerate(segments_iter)
            ]
        except Exception as exc:
            raise TranscriptionError(
                "Não foi possível transcrever o áudio com faster-whisper.\n\n"
                f"Causa provável: {exc}\n\n"
                "Verifique se há espaço em disco disponível e conexão com a "
                "internet (necessária no primeiro uso, para baixar o modelo "
                f"'{self._model_size}')."
            ) from exc

        return TranscriptionResult(language=info.language, segments=segments)


@dataclass(frozen=True)
class TranscribeResult:
    md_path: Path
    json_path: Path
    skipped: bool


def transcribe_project(project_dir: Path, settings: Settings, *, force: bool = False) -> TranscribeResult:
    audio_path = project_dir / "audio" / "audio.wav"
    if not audio_path.exists():
        raise TranscriptionError(
            "Áudio não encontrado.\n\n"
            f"Esperado em: {audio_path}\n\n"
            "Execute 'video-editorial audio PROJECT' primeiro."
        )

    md_path = project_dir / _MD_FILENAME
    json_path = project_dir / _JSON_FILENAME

    if md_path.exists() and not force:
        return TranscribeResult(md_path=md_path, json_path=json_path, skipped=True)

    provider = FasterWhisperProvider(model_size=settings.whisper_model, language=settings.whisper_language)
    result = provider.transcribe(audio_path)

    _write_markdown(md_path, result)
    _write_json(json_path, result)

    return TranscribeResult(md_path=md_path, json_path=json_path, skipped=False)


def _write_markdown(md_path: Path, result: TranscriptionResult) -> None:
    lines = ["# Transcrição", "", f"Idioma detectado: {result.language}", ""]
    for segment in result.segments:
        start = _format_timestamp(segment.start_seconds)
        end = _format_timestamp(segment.end_seconds)
        lines.append(f"[{start} → {end}]")
        lines.append(segment.text)
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(json_path: Path, result: TranscriptionResult) -> None:
    data = {
        "language": result.language,
        "segments": [
            {
                "index": segment.index,
                "start": segment.start_seconds,
                "end": segment.end_seconds,
                "text": segment.text,
            }
            for segment in result.segments
        ],
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_timestamp(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
