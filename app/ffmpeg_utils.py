"""Helpers compartilhados para chamadas a `ffmpeg`/`ffprobe` via subprocess.

Extraído da duplicação que já existia entre `app/analysis.py`
(`get_video_duration_seconds`, via `ffprobe`) e `app/cutter.py`
(`_run_ffmpeg_cut`, via `ffmpeg`). Não define um tipo de exceção próprio —
cada chamador continua lançando seu próprio erro de domínio
(`AnalysisError`, `CutterError`, etc.) com a mensagem que faz sentido para
quem lê aquele fluxo.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

INSTALL_HINT = "Instale no macOS:\n\nbrew install ffmpeg"

_STDERR_TRUNCATE_CHARS = 2000
_DEFAULT_SAMPLE_RATE = 48000


def is_binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def truncate_stderr(stderr: str) -> str:
    return stderr.strip()[-_STDERR_TRUNCATE_CHARS:]


@dataclass(frozen=True)
class VideoProperties:
    width: int
    height: int
    fps: float
    sample_rate: int


def probe_video_properties(video_path: Path) -> VideoProperties:
    """Resolução/FPS/sample rate de áudio de um vídeo, via `ffprobe`.

    Usado por `app/editorial_renderer.py` para gerar intro/CTA com os
    mesmos parâmetros do corte, condição necessária para o filtro
    `concat` funcionar corretamente. Levanta `RuntimeError` em falha —
    este módulo não define exceção de domínio própria; quem chama
    (`app/editorial_renderer.py`) converte para seu próprio erro.
    """
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,sample_rate",
            "-of",
            "json",
            str(video_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe falhou ao inspecionar '{video_path}':\n\n{truncate_stderr(result.stderr)}"
        )

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise RuntimeError(f"Nenhuma trilha de vídeo encontrada em '{video_path}'.")

    sample_rate = _DEFAULT_SAMPLE_RATE
    if audio_stream and audio_stream.get("sample_rate"):
        sample_rate = int(audio_stream["sample_rate"])

    return VideoProperties(
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=_parse_frame_rate(video_stream.get("r_frame_rate", "30/1")),
        sample_rate=sample_rate,
    )


def _parse_frame_rate(raw: str) -> float:
    if "/" in raw:
        numerator, denominator = raw.split("/")
        denominator = float(denominator)
        return float(numerator) / denominator if denominator else 0.0
    return float(raw)
