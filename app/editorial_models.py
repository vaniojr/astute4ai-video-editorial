"""Modelo do plano editorial final, já validado (pós `app/editorial_planner.py`).

Não duplica o modelo de capítulo — `AnalysisRow`/`ChapterReport` (`app/analysis.py`)
continuam sendo a única representação de um capítulo do `03 Analise.csv`.
Estas estruturas representam só o plano editorial derivado dele.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ContextCard:
    kind: str  # "context" | "subtopic"
    text: str
    timestamp: float  # segundos, relativo ao início do corte — sempre calculado pelo código


@dataclass(frozen=True)
class Highlight:
    text: str
    start: float  # segundos, relativo ao início do corte
    end: float


@dataclass(frozen=True)
class SourceAttribution:
    text: str


@dataclass(frozen=True)
class Cta:
    """Exatamente um entre `text`/`image`/`video` quando `enabled=True` —

    garantido na origem por `app/brands.py::_validate_features` (o brand
    profile já não carrega se tiver zero ou mais de uma opção configurada),
    então o restante do pipeline confia nessa invariante sem revalidar.
    """

    enabled: bool
    text: Optional[str] = None
    image: Optional[str] = None
    video: Optional[str] = None


@dataclass(frozen=True)
class Intro:
    mode: str  # "text_only" | "disabled"
    text: Optional[str] = None


@dataclass(frozen=True)
class EditorialPlan:
    chapter: str
    cut_file: str
    brand: str
    version: int
    intro: Intro
    source_attribution: SourceAttribution
    lower_thirds: List[str] = field(default_factory=list)  # sempre vazio nesta entrega
    context_cards: List[ContextCard] = field(default_factory=list)
    highlights: List[Highlight] = field(default_factory=list)
    cta: Cta = field(default_factory=lambda: Cta(enabled=False))
    provider: str = ""
    model: str = ""
