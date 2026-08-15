"""Abstração de provider de planejamento editorial.

A IA nunca decide um timestamp absoluto ou relativo em segundos — só
propõe texto (intro, cards, citação de destaque) e, quando precisa de
posição, uma fração 0.0-1.0 da duração do corte (`RawContextCard`) ou o
texto exato de uma citação a ser localizada na transcrição
(`RawHighlight`). Quem converte fração→segundo e resolve o timestamp real
de uma citação é sempre `app/editorial_planner.py` — nunca o provider
(Feature_Editorializacao_Automatica.md seção 34).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

_SUPPORTED_PROVIDERS = ("claude",)


class EditorialProviderError(Exception):
    """Erro acionável do provider de planejamento editorial."""


@dataclass(frozen=True)
class EditorialRequest:
    tema_principal: str
    titulo_sugerido: str
    resumo: str
    pergunta_principal: str
    trecho_para_validar_primeiro: str
    observacoes: str
    transcript_excerpt: str
    source_title: str
    source_channel: str
    system_instructions: str
    editorial_instructions: str


@dataclass(frozen=True)
class RawContextCard:
    kind: str  # "context" | "subtopic"
    text: str
    position_fraction: float  # 0.0-1.0, sugestão da IA; a conversão para segundos é do planner


@dataclass(frozen=True)
class RawHighlight:
    quote: str  # citação a ser localizada na transcrição pelo planner; nunca um timestamp


@dataclass(frozen=True)
class EditorialCandidate:
    intro_text: str
    context_cards: List[RawContextCard] = field(default_factory=list)
    highlights: List[RawHighlight] = field(default_factory=list)


@dataclass(frozen=True)
class EditorialUsageInfo:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class EditorialResult:
    candidate: EditorialCandidate
    provider: str
    model: str
    usage: Optional[EditorialUsageInfo] = None


class EditorialProvider(ABC):
    @abstractmethod
    def plan(self, request: EditorialRequest) -> EditorialResult: ...


def get_editorial_provider(name: str, *, model: str, temperature: float) -> EditorialProvider:
    if name == "claude":
        from app.editorial_claude_provider import ClaudeEditorialProvider

        return ClaudeEditorialProvider(model=model, temperature=temperature)
    raise EditorialProviderError(
        f"Provider de editorialização '{name}' ainda não implementado. "
        f"Disponíveis: {', '.join(_SUPPORTED_PROVIDERS)}."
    )
