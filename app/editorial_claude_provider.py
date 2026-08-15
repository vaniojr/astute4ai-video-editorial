"""Provider de planejamento editorial via API da Claude (Anthropic).

Único módulo desta feature que importa o SDK `anthropic` — `app/editorial_planner.py`
e `app/editorial_service.py` nunca dependem dele, mesmo padrão de isolamento
já usado em `app/claude_provider.py` para a análise editorial. Structured
output via tool use: a Claude é forçada a chamar uma única ferramenta cujo
schema já restringe os campos, e o resultado ainda passa pela validação de
`app/editorial_planner.py` (conversão de posição→segundo, verificação de
citações contra a transcrição real) — a saída do modelo nunca é timestamp,
sempre texto/posição relativa tratada como dado, nunca como verdade aceita
silenciosamente.
"""

import os
from typing import Any, Dict, List

import anthropic

from app.editorial_provider import (
    EditorialCandidate,
    EditorialProvider,
    EditorialProviderError,
    EditorialRequest,
    EditorialResult,
    EditorialUsageInfo,
    RawContextCard,
    RawHighlight,
)

_TOOL_NAME = "submeter_plano_editorial"
_MAX_TOKENS = 4096

_CARD_KIND_VALUES = ["context", "subtopic"]

_TOOL_DEFINITION: Dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Submete o plano editorial (intro, cards de contexto/subtema, destaques) para um corte.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intro_text": {
                "type": "string",
                "description": (
                    "Texto curto de intro (8-15s de leitura), explicando o contexto do corte "
                    "sem inventar fatos. String vazia se nenhuma intro fizer sentido."
                ),
            },
            "context_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": _CARD_KIND_VALUES},
                        "text": {"type": "string"},
                        "position_fraction": {
                            "type": "number",
                            "description": "Posição sugerida dentro do corte, de 0.0 (início) a 1.0 (final).",
                        },
                    },
                    "required": ["kind", "text", "position_fraction"],
                },
            },
            "highlights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {
                            "type": "string",
                            "description": (
                                "Citação copiada literalmente da transcrição fornecida. "
                                "Nunca invente ou parafraseie."
                            ),
                        },
                    },
                    "required": ["quote"],
                },
            },
        },
        "required": ["intro_text", "context_cards", "highlights"],
    },
}


class ClaudeEditorialProvider(EditorialProvider):
    def __init__(self, model: str, temperature: float, *, max_retries: int = 3):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise EditorialProviderError(
                "ANTHROPIC_API_KEY não definida.\n\n"
                "Defina a variável de ambiente ou crie um arquivo .env "
                "(veja .env.example) antes de rodar 'editorialize'."
            )
        self._model = model
        self._temperature = temperature
        self._client = anthropic.Anthropic(max_retries=max_retries)

    def plan(self, request: EditorialRequest) -> EditorialResult:
        # `temperature` não é enviado — mesma descoberta já feita em
        # app/claude_provider.py (rejeitado por modelos como claude-sonnet-5).
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=request.system_instructions,
                tools=[_TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": _build_user_message(request)}],
            )
        except anthropic.AuthenticationError as exc:
            raise EditorialProviderError(
                "Credencial inválida para a API da Claude (ANTHROPIC_API_KEY)."
            ) from exc
        except anthropic.AnthropicError as exc:
            raise EditorialProviderError(f"Falha ao chamar a API da Claude: {exc}") from exc

        tool_use = next(
            (block for block in message.content if getattr(block, "type", None) == "tool_use"), None
        )
        if tool_use is None:
            raise EditorialProviderError(
                "A resposta da Claude não incluiu o resultado estruturado esperado."
            )

        candidate = _parse_candidate(tool_use.input)

        usage = None
        if message.usage is not None:
            usage = EditorialUsageInfo(
                input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens
            )

        return EditorialResult(candidate=candidate, provider="claude", model=self._model, usage=usage)


def _build_user_message(request: EditorialRequest) -> str:
    return (
        f"{request.editorial_instructions}\n\n"
        "---\n\n"
        f"## Metadados\n\nFonte: {request.source_title} ({request.source_channel})\n\n"
        "---\n\n"
        "## Dados do capítulo (03 Analise.csv)\n\n"
        f"Tema Principal: {request.tema_principal}\n"
        f"Título Sugerido: {request.titulo_sugerido}\n"
        f"Resumo: {request.resumo}\n"
        f"Pergunta Principal: {request.pergunta_principal}\n"
        f"Trecho para Validar Primeiro: {request.trecho_para_validar_primeiro}\n"
        f"Observações: {request.observacoes}\n\n"
        "---\n\n"
        f"## Transcrição deste corte (timestamps relativos ao início do corte)\n\n"
        f"{request.transcript_excerpt}"
    )


def _parse_candidate(raw_input: Any) -> EditorialCandidate:
    if not isinstance(raw_input, dict):
        raise EditorialProviderError("Resposta estruturada da Claude não é um objeto válido.")

    try:
        intro_text = str(raw_input["intro_text"])
        raw_cards = raw_input["context_cards"]
        raw_highlights = raw_input["highlights"]
    except KeyError as exc:
        raise EditorialProviderError(f"Campo obrigatório ausente na resposta da Claude: {exc}") from exc

    if not isinstance(raw_cards, list) or not isinstance(raw_highlights, list):
        raise EditorialProviderError("'context_cards'/'highlights' na resposta deveriam ser listas.")

    context_cards: List[RawContextCard] = []
    for index, raw_card in enumerate(raw_cards):
        if not isinstance(raw_card, dict):
            raise EditorialProviderError(f"Card {index} da resposta não é um objeto válido.")
        try:
            context_cards.append(
                RawContextCard(
                    kind=str(raw_card["kind"]),
                    text=str(raw_card["text"]),
                    position_fraction=float(raw_card["position_fraction"]),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise EditorialProviderError(f"Card {index} da resposta está incompleto ou mal formatado: {exc}") from exc

    highlights: List[RawHighlight] = []
    for index, raw_highlight in enumerate(raw_highlights):
        if not isinstance(raw_highlight, dict):
            raise EditorialProviderError(f"Destaque {index} da resposta não é um objeto válido.")
        try:
            highlights.append(RawHighlight(quote=str(raw_highlight["quote"])))
        except (KeyError, ValueError, TypeError) as exc:
            raise EditorialProviderError(
                f"Destaque {index} da resposta está incompleto ou mal formatado: {exc}"
            ) from exc

    return EditorialCandidate(intro_text=intro_text, context_cards=context_cards, highlights=highlights)
