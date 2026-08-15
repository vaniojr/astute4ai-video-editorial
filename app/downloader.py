"""Download do vídeo original via yt-dlp (PRD seção 11).

Apenas o download do arquivo já registrado em `project.json` (`source_url`).
A consulta de metadados usada na criação do projeto vive em `app/metadata.py`.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yt_dlp

from app.config import Settings

_FINAL_FILENAME = "video-original.mp4"


class DownloadError(Exception):
    """Erro acionável ao baixar o vídeo original."""


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    skipped: bool


def download_video(project_dir: Path, source_url: str, settings: Settings, *, force: bool = False) -> DownloadResult:
    original_dir = project_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    final_path = original_dir / _FINAL_FILENAME

    if final_path.exists() and not force:
        return DownloadResult(path=final_path, skipped=True)

    if force:
        for existing in original_dir.iterdir():
            if existing.is_file():
                existing.unlink()

    if shutil.which("ffmpeg") is None:
        raise DownloadError(
            "FFmpeg não foi encontrado.\n\n"
            "Instale no macOS:\n\n"
            "brew install ffmpeg"
        )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": _build_format_selector(settings.max_video_height),
        "merge_output_format": "mp4",
        "outtmpl": str(original_dir / "video-original.%(ext)s"),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(source_url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(
            "Não foi possível baixar o vídeo.\n\n"
            f"URL: {source_url}\n"
            f"Causa provável: {exc}\n\n"
            "Verifique se a URL está correta, se o vídeo é público/disponível "
            "e se há conexão com a internet."
        ) from exc

    if not final_path.exists():
        raise DownloadError(
            "O download foi concluído, mas o arquivo final não foi encontrado em "
            f"{final_path}.\n\n"
            "Verifique se o FFmpeg está instalado corretamente para permitir a "
            "conversão/combinação para MP4."
        )

    return DownloadResult(path=final_path, skipped=False)


def _build_format_selector(max_video_height: Optional[int]) -> str:
    if max_video_height:
        return f"bestvideo[height<={max_video_height}]+bestaudio/best[height<={max_video_height}]"
    return "bestvideo+bestaudio/best"
