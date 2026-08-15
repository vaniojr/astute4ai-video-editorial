"""Provider de geração de imagem para thumbnail via API da OpenAI (`gpt-image-1`).

Único módulo que importa o SDK `openai` — `app/thumbnail_service.py` nunca
depende dele, mesmo isolamento já usado por `app/claude_provider.py`/
`app/editorial_claude_provider.py`.

Usa `images.edit()`, não `images.generate()` — só o endpoint de edição
aceita múltiplas imagens de referência como entrada, o que permite
preservar a identidade visual real dos participantes a partir dos frames
reais extraídos do corte (Feature_thumbnail.md seção 2), em vez de gerar
rostos do zero a partir de um prompt textual.
"""

import base64
import os
from typing import List, Optional

import openai

from app.brands import Brand
from app.thumbnail_provider import (
    ThumbnailImageResult,
    ThumbnailProvider,
    ThumbnailProviderError,
    ThumbnailRequest,
    ThumbnailResult,
)

_RESTRICOES = (
    "Não invente participantes que não estejam nas imagens de referência anexadas.\n"
    "Não apresente nenhuma alegação não verificada como fato no texto da thumbnail.\n"
    "Priorize rosto/personagem em destaque, texto curto e legível, alto contraste."
)


class OpenAIThumbnailProvider(ThumbnailProvider):
    def __init__(self, model: str):
        if not os.environ.get("OPENAI_API_KEY"):
            raise ThumbnailProviderError(
                "OPENAI_API_KEY não definida.\n\n"
                "Defina a variável de ambiente ou crie um arquivo .env "
                "(veja .env.example) antes de usar '--provider openai'."
            )
        self._model = model
        self._client = openai.OpenAI()

    def generate(self, request: ThumbnailRequest) -> ThumbnailResult:
        if not request.reference_images:
            raise ThumbnailProviderError("Nenhum frame de referência disponível para gerar a thumbnail.")

        size = _resolve_size(request.brand)
        prompt = _build_prompt(request)

        opened_files = [path.open("rb") for path in request.reference_images]
        try:
            response = self._client.images.edit(
                model=self._model,
                image=opened_files,
                prompt=prompt,
                size=size,
                n=1,
            )
        except openai.AuthenticationError as exc:
            raise ThumbnailProviderError(
                "Credencial inválida para a API da OpenAI (OPENAI_API_KEY)."
            ) from exc
        except openai.OpenAIError as exc:
            raise ThumbnailProviderError(f"Falha ao chamar a API da OpenAI: {exc}") from exc
        finally:
            for handle in opened_files:
                handle.close()

        if not response.data:
            raise ThumbnailProviderError("A resposta da OpenAI não incluiu nenhuma imagem.")

        images: List[ThumbnailImageResult] = []
        for item in response.data:
            if not item.b64_json:
                continue
            images.append(
                ThumbnailImageResult(content=base64.b64decode(item.b64_json), content_type="image/png")
            )

        if not images:
            raise ThumbnailProviderError("A resposta da OpenAI não incluiu dados de imagem (b64_json).")

        return ThumbnailResult(images=images, provider="openai")


def _resolve_size(brand: Optional[Brand]) -> str:
    if brand is None:
        return "1536x1024"
    width = brand.thumbnail.width
    height = brand.thumbnail.height
    if width == height:
        return "1024x1024"
    if width > height:
        return "1536x1024"
    return "1024x1536"


def _build_prompt(request: ThumbnailRequest) -> str:
    brand_section = ""
    if request.brand is not None:
        colors = request.brand.colors
        brand_section = (
            f"\n\nDireção visual da marca '{request.brand.name}':\n"
            f"- Estilo: {request.brand.thumbnail.style or '(não definido)'}\n"
            f"- Cor primária: {colors.primary or '-'}\n"
            f"- Cor de fundo: {colors.background or '-'}\n"
            f"- Cor de texto: {colors.text or '-'}\n"
            f"- Cor de destaque: {colors.accent or '-'}"
        )

    return (
        f"Gere uma thumbnail de vídeo em formato {request.aspect_ratio} para publicação.\n\n"
        "Use as imagens em anexo como base visual real — preserve a identidade visual real "
        "das pessoas mostradas, não invente rostos nem substitua por pessoas diferentes.\n\n"
        f"Briefing editorial:\n\n{request.briefing}"
        f"{brand_section}\n\n"
        f"Restrições:\n{_RESTRICOES}"
    )
