"""Helpers compartilhados para chamadas a `ffmpeg`/`ffprobe` via subprocess.

Extraído da duplicação que já existia entre `app/analysis.py`
(`get_video_duration_seconds`, via `ffprobe`) e `app/cutter.py`
(`_run_ffmpeg_cut`, via `ffmpeg`). Não define um tipo de exceção próprio —
cada chamador continua lançando seu próprio erro de domínio
(`AnalysisError`, `CutterError`, etc.) com a mensagem que faz sentido para
quem lê aquele fluxo.
"""

import shutil
import subprocess
from typing import List

INSTALL_HINT = "Instale no macOS:\n\nbrew install ffmpeg"

_STDERR_TRUNCATE_CHARS = 2000


def is_binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def truncate_stderr(stderr: str) -> str:
    return stderr.strip()[-_STDERR_TRUNCATE_CHARS:]
