"""Abstração de provider de geração de imagem para thumbnail.

Nenhum SDK de provider real é importado aqui — só no arquivo do provider
concreto (ex.: `app/thumbnail_openai_provider.py`), mesmo isolamento já
usado por `app/claude_provider.py`/`app/editorial_claude_provider.py`.
"manual" nunca gera imagem nenhuma (Feature_thumbnail.md seção 27/28):
frames + briefing continuam disponíveis para uso manual, sem falhar o
pipeline.

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

SUPPORTED_PROVIDERS = ("manual", "openai")


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


def is_supported_provider(name: str) -> bool:
    """Checa o nome sem construir nada — nunca exige credencial.

    Usado por `plan_thumbnail()` (`--dry-run`) para validar `--provider`
    cedo, sem o custo colateral de `get_thumbnail_provider()` já
    construir o provider real (que exigiria a API key mesmo em dry-run).
    """
    return name in SUPPORTED_PROVIDERS


def get_thumbnail_provider(name: str, *, model: Optional[str] = None) -> ThumbnailProvider:
    if name == "manual":
        return ManualThumbnailProvider()
    if name == "openai":
        from app.thumbnail_openai_provider import OpenAIThumbnailProvider

        return OpenAIThumbnailProvider(model=model or "gpt-image-1")
    raise ThumbnailProviderError(
        f"Provider de thumbnail '{name}' ainda não implementado. "
        f"Disponíveis: {', '.join(SUPPORTED_PROVIDERS)}."
    )
