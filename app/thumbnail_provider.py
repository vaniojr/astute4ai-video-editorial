"""Abstração de provider de geração de imagem para thumbnail.

Nenhum SDK de provider real (OpenAI/Google/etc.) é importado aqui nem em
nenhum outro módulo do projeto enquanto nenhum provider real estiver
implementado — só "manual" existe por enquanto, e ele nunca gera imagem
nenhuma (Feature_thumbnail.md seção 27/28): frames + briefing continuam
disponíveis para uso manual, sem falhar o pipeline.

O provider só gera bytes de imagem — nunca decide nome de arquivo ou
versão. Quem aplica `app/versioning.py` e grava o arquivo final é
`app/thumbnail_service.py`, mesma separação que `app/cutter.py` já usa
(a IA nunca decide nome de arquivo/timestamp).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.brands import Brand

_SUPPORTED_PROVIDERS = ("manual",)


class ThumbnailProviderError(Exception):
    """Erro acionável do provider de geração de imagem."""


@dataclass(frozen=True)
class ThumbnailRequest:
    reference_images: List[Path]
    briefing: str
    aspect_ratio: str = "16:9"
    brand: Optional[Brand] = None


@dataclass(frozen=True)
class ThumbnailImageResult:
    content: bytes
    content_type: str = "image/png"


@dataclass(frozen=True)
class ThumbnailResult:
    images: List[ThumbnailImageResult] = field(default_factory=list)
    provider: str = ""


class ThumbnailProvider(ABC):
    @abstractmethod
    def generate(self, request: ThumbnailRequest) -> ThumbnailResult: ...


class ManualThumbnailProvider(ThumbnailProvider):
    """Nunca gera imagem — frames + briefing ficam prontos para uso manual."""

    def generate(self, request: ThumbnailRequest) -> ThumbnailResult:
        return ThumbnailResult(images=[], provider="manual")


def get_thumbnail_provider(name: str) -> ThumbnailProvider:
    if name == "manual":
        return ManualThumbnailProvider()
    raise ThumbnailProviderError(
        f"Provider de thumbnail '{name}' ainda não implementado. "
        f"Disponíveis: {', '.join(_SUPPORTED_PROVIDERS)}."
    )
