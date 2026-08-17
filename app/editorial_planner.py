"""Validação/conversão da saída do provider em um `EditorialPlan` final.

Duas regras centrais (Feature_Editorializacao_Automatica.md seção 34):
posição de card é sempre fração 0.0-1.0 convertida para segundos aqui,
nunca aceita como segundo absoluto/relativo vindo da IA; e citações de
destaque só viram `Highlight` se o texto realmente aparecer na
transcrição do corte — caso contrário são descartadas silenciosamente
(nunca inventa quote, seção 14).
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from app.brands import Brand
from app.editorial_models import ContextCard, Cta, EditorialPlan, Highlight, Intro, SourceAttribution
from app.editorial_provider import EditorialCandidate
from app.project import Project
from app.timestamps import format_hms, to_relative_seconds
from app.transcriber import TranscriptSegment

# Cap defensivo contra o modelo devolver mais cards do que o prompt pede
# (Feature_Editorializacao_Automatica.md seção 12: "0 a 4 cards por corte").
_MAX_CONTEXT_CARDS = 4


def extract_transcript_excerpt(
    transcricao_json_path: Path, start_seconds: float, end_seconds: float
) -> List[TranscriptSegment]:
    """Segmentos da transcrição cobertos pelo intervalo do capítulo, com
    timestamps já convertidos para relativos ao início do corte.
    """
    data = json.loads(transcricao_json_path.read_text(encoding="utf-8"))

    segments = []
    for raw in data.get("segments", []):
        seg_start = raw["start"]
        seg_end = raw["end"]
        if seg_end < start_seconds or seg_start > end_seconds:
            continue
        segments.append(
            TranscriptSegment(
                index=raw["index"],
                start_seconds=to_relative_seconds(seg_start, start_seconds),
                end_seconds=to_relative_seconds(seg_end, start_seconds),
                text=raw["text"],
            )
        )
    return segments


def format_transcript_excerpt(segments: List[TranscriptSegment]) -> str:
    return "\n".join(f"[{format_hms(s.start_seconds)} → {format_hms(s.end_seconds)}] {s.text}" for s in segments)


def find_highlight_timing(
    quote: str, segments: List[TranscriptSegment]
) -> Optional[Tuple[float, float]]:
    """Localiza `quote` nos segmentos reais da transcrição do corte.

    Tenta primeiro um único segmento; depois pares de segmentos adjacentes
    (citação que atravessa a borda de um segmento). Retorna `None` se não
    encontrar — o chamador descarta o destaque nesse caso.
    """
    normalized_quote = _normalize(quote)
    if not normalized_quote:
        return None

    for segment in segments:
        if normalized_quote in _normalize(segment.text):
            return segment.start_seconds, segment.end_seconds

    for a, b in zip(segments, segments[1:]):
        combined = f"{_normalize(a.text)} {_normalize(b.text)}"
        if normalized_quote in combined:
            return a.start_seconds, b.end_seconds

    return None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def build_editorial_plan(
    candidate: EditorialCandidate,
    *,
    chapter: str,
    cut_file: str,
    brand: Brand,
    project: Project,
    version: int,
    provider: str,
    model: str,
    cut_duration_seconds: float,
    transcript_segments: List[TranscriptSegment],
) -> EditorialPlan:
    intro_text = candidate.intro_text.strip()
    intro = Intro(mode="text_only", text=intro_text) if intro_text else Intro(mode="disabled", text=None)

    source_text = f"Fonte original: {project.title}"
    if project.channel:
        source_text = f"{source_text} ({project.channel})"

    context_cards = []
    for raw_card in candidate.context_cards[:_MAX_CONTEXT_CARDS]:
        fraction = min(max(raw_card.position_fraction, 0.0), 1.0)
        timestamp = round(fraction * cut_duration_seconds, 2)
        context_cards.append(ContextCard(kind=raw_card.kind, text=raw_card.text, timestamp=timestamp))

    highlights = []
    for raw_highlight in candidate.highlights:
        timing = find_highlight_timing(raw_highlight.quote, transcript_segments)
        if timing is None:
            continue
        start, end = timing
        highlights.append(Highlight(text=raw_highlight.quote, start=start, end=end))

    cta = Cta(enabled=False)
    if brand.features.cta_enabled:
        if brand.video.cta_text:
            cta = Cta(enabled=True, text=brand.video.cta_text)
        elif brand.video.cta_image:
            cta = Cta(enabled=True, image=str(brand.video.cta_image))
        elif brand.video.cta_video:
            cta = Cta(enabled=True, video=str(brand.video.cta_video))

    return EditorialPlan(
        chapter=chapter,
        cut_file=cut_file,
        brand=brand.slug,
        version=version,
        intro=intro,
        source_attribution=SourceAttribution(text=source_text),
        lower_thirds=[],
        context_cards=context_cards,
        highlights=highlights,
        cta=cta,
        provider=provider,
        model=model,
    )
