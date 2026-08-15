"""Configuração central da aplicação (PRD seção 29).

Valores lidos de variáveis de ambiente quando presentes, com defaults
sensatos caso contrário. Apenas `projetos_dir` é utilizado nesta entrega;
os demais campos estão reservados para as entregas de áudio, transcrição
e cortes, evitando constantes espalhadas pelo código.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Settings:
    projetos_dir: Path
    whisper_model: str
    whisper_language: str
    ffmpeg_crf: int
    ffmpeg_preset: str
    audio_bitrate_kbps: int
    output_format: str
    max_video_height: Optional[int]


def load_settings() -> Settings:
    max_video_height_raw = os.environ.get("VIDEO_EDITORIAL_MAX_VIDEO_HEIGHT")
    return Settings(
        projetos_dir=Path(os.environ.get("VIDEO_EDITORIAL_PROJETOS_DIR", "projetos")),
        whisper_model=os.environ.get("VIDEO_EDITORIAL_WHISPER_MODEL", "medium"),
        whisper_language=os.environ.get("VIDEO_EDITORIAL_WHISPER_LANGUAGE", "pt"),
        ffmpeg_crf=int(os.environ.get("VIDEO_EDITORIAL_FFMPEG_CRF", "18")),
        ffmpeg_preset=os.environ.get("VIDEO_EDITORIAL_FFMPEG_PRESET", "medium"),
        audio_bitrate_kbps=int(os.environ.get("VIDEO_EDITORIAL_AUDIO_BITRATE_KBPS", "192")),
        output_format=os.environ.get("VIDEO_EDITORIAL_OUTPUT_FORMAT", "mp4"),
        max_video_height=int(max_video_height_raw) if max_video_height_raw else None,
    )
