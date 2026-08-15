"""Extração de frames reais do corte para uso como base da thumbnail.

Extrai sempre do arquivo de corte (`cortes/*.mp4`), nunca do vídeo
original — o corte já está no intervalo editorial certo, sem precisar
converter timestamp absoluto (do vídeo original) para relativo (do corte).
Posições fixas, igualmente espaçadas — cobrem início/25%/50%/75%/final do
corte como casos particulares do espaçamento uniforme (Feature_thumbnail.md
seção 8). Sem heurística de qualidade de imagem (olhos fechados/motion
blur/etc.) nesta fase — o próprio documento de referência permite regra
simples no MVP.
"""

from pathlib import Path
from typing import List

from app.ffmpeg_utils import INSTALL_HINT as FFMPEG_INSTALL_HINT
from app.ffmpeg_utils import is_binary_available, run, truncate_stderr

FRAME_COUNT = 9
_END_EPSILON_SECONDS = 0.1


class ThumbnailFramesError(Exception):
    """Erro acionável na extração de frames."""


def compute_frame_offsets(duration_seconds: float, count: int = FRAME_COUNT) -> List[float]:
    if duration_seconds <= 0:
        raise ThumbnailFramesError(f"Duração inválida para extração de frames: {duration_seconds}")
    if count < 2:
        raise ThumbnailFramesError("count deve ser >= 2 para cobrir início e final do corte.")

    last_offset = max(duration_seconds - _END_EPSILON_SECONDS, 0.0)
    step = last_offset / (count - 1)
    return [round(step * i, 2) for i in range(count)]


def extract_frames(
    cut_path: Path, output_dir: Path, duration_seconds: float, *, count: int = FRAME_COUNT
) -> List[Path]:
    if not is_binary_available("ffmpeg"):
        raise ThumbnailFramesError(f"FFmpeg não foi encontrado.\n\n{FFMPEG_INSTALL_HINT}")

    output_dir.mkdir(parents=True, exist_ok=True)
    offsets = compute_frame_offsets(duration_seconds, count)

    frame_paths = []
    for index, offset in enumerate(offsets, start=1):
        frame_path = output_dir / f"frame-{index:02d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(offset),
            "-i",
            str(cut_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ]
        result = run(cmd)
        if result.returncode != 0:
            raise ThumbnailFramesError(
                f"FFmpeg falhou ao extrair frame em {offset}s de "
                f"'{cut_path.name}':\n\n{truncate_stderr(result.stderr)}"
            )
        frame_paths.append(frame_path)

    return frame_paths
