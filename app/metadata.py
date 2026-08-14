"""Consulta de metadados de vídeos via yt-dlp (PRD seção 5.1).

Apenas consulta metadados (``download=False``). O download do arquivo de
vídeo em si pertence à Entrega 2 e não é feito por este módulo.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import yt_dlp


class MetadataError(Exception):
    """Erro acionável ao consultar metadados de um vídeo."""


@dataclass(frozen=True)
class VideoMetadata:
    platform: str
    source_id: str
    source_url: str
    title: str
    channel: Optional[str]
    published_at: Optional[date]
    duration_seconds: Optional[int]


def fetch_metadata(url: str) -> VideoMetadata:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise MetadataError(
            "Não foi possível obter metadados do vídeo.\n\n"
            f"URL: {url}\n"
            f"Causa provável: {exc}\n\n"
            "Verifique se a URL está correta, se o vídeo é público/disponível "
            "e se há conexão com a internet."
        ) from exc

    if info is None:
        raise MetadataError(f"Nenhuma informação retornada para a URL: {url}")

    source_id = info.get("id")
    if not source_id:
        raise MetadataError(
            f"Não foi possível identificar o ID do vídeo a partir da URL: {url}"
        )

    title = info.get("title")
    if not title:
        raise MetadataError(
            f"Não foi possível identificar o título do vídeo a partir da URL: {url}"
        )

    duration = info.get("duration")

    return VideoMetadata(
        platform="youtube",
        source_id=source_id,
        source_url=url,
        title=title,
        channel=info.get("channel") or info.get("uploader"),
        published_at=_parse_upload_date(info.get("upload_date")),
        duration_seconds=int(duration) if duration is not None else None,
    )


def _parse_upload_date(raw: Optional[str]) -> Optional[date]:
    if not raw or len(raw) != 8:
        return None
    try:
        return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None
