"""Extração de áudio do vídeo original via FFmpeg/ffprobe (PRD seção 12).

O áudio é derivado do vídeo já baixado (`original/video-original.mp4`) —
nunca baixado de novo. `ffmpeg`/`ffprobe` são binários externos, chamados
via `subprocess` (diferente do `yt-dlp`, que expõe uma API Python).
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SAMPLE_RATE_HZ = 16000
_CHANNELS = 1
_FINAL_FILENAME = "audio.wav"


class AudioError(Exception):
    """Erro acionável ao extrair o áudio do vídeo original."""


@dataclass(frozen=True)
class AudioResult:
    path: Path
    skipped: bool


def extract_audio(project_dir: Path, *, force: bool = False) -> AudioResult:
    video_path = project_dir / "original" / "video-original.mp4"
    if not video_path.exists():
        raise AudioError(
            "Vídeo original não encontrado.\n\n"
            f"Esperado em: {video_path}\n\n"
            "Execute 'video-editorial download PROJECT' primeiro."
        )

    audio_dir = project_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    final_path = audio_dir / _FINAL_FILENAME

    if final_path.exists() and not force:
        return AudioResult(path=final_path, skipped=True)

    if final_path.exists():
        final_path.unlink()

    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise AudioError(
            "FFmpeg não foi encontrado.\n\n"
            "Instale no macOS:\n\n"
            "brew install ffmpeg"
        )

    _validate_has_audio_stream(video_path)

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            str(_CHANNELS),
            "-ar",
            str(_SAMPLE_RATE_HZ),
            str(final_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioError(
            "Falha ao extrair o áudio com FFmpeg.\n\n" + _tail(result.stderr)
        )

    if not final_path.exists():
        raise AudioError(
            f"A extração terminou, mas o arquivo final não foi encontrado em {final_path}."
        )

    return AudioResult(path=final_path, skipped=False)


def _validate_has_audio_stream(video_path: Path) -> None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioError(
            "Não foi possível ler o vídeo original com ffprobe.\n\n"
            + _tail(result.stderr)
            + "\n\nO arquivo pode estar corrompido ou incompleto. Tente "
            "'video-editorial download PROJECT --force'."
        )
    if "audio" not in result.stdout:
        raise AudioError(
            "O vídeo original não possui trilha de áudio detectável.\n\n"
            f"Arquivo: {video_path}"
        )


def _tail(text: str, max_lines: int = 10) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-max_lines:])
