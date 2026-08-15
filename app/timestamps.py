"""Parser de timestamps com desambiguação usando a duração do vídeo (PRD seção 17).

Formatos suportados: `MM:SS`, `H:MM:SS`, e as variantes corrompidas por
planilhas que anexam um componente `:00` espúrio (`MM:SS:00`, `H:MM:SS:00`).
Nunca adivinha silenciosamente: quando a duração do vídeo não permite
determinar com segurança qual leitura é a correta, levanta
`TimestampAmbiguousError` em vez de escolher uma das opções.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


class TimestampFormatError(Exception):
    """O texto não corresponde a nenhum formato de timestamp reconhecido."""


class TimestampOutOfRangeError(Exception):
    """A única leitura sensata do timestamp excede a duração do vídeo."""

    def __init__(self, raw: str, seconds: float, duration_seconds: float):
        self.raw = raw
        self.seconds = seconds
        self.duration_seconds = duration_seconds
        super().__init__(
            f"O timestamp '{raw}' ({format_hms(seconds)}) excede a duração do "
            f"vídeo ({format_hms(duration_seconds)})."
        )


class TimestampAmbiguousError(Exception):
    """O timestamp admite mais de uma leitura e não foi possível desambiguar."""

    def __init__(self, raw: str, duration_seconds: Optional[float], candidates: List[Tuple[str, float]]):
        self.raw = raw
        self.duration_seconds = duration_seconds
        self.candidates = candidates
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [f"O timestamp '{self.raw}' é ambíguo.", ""]
        if self.duration_seconds is not None:
            lines.append(f"Duração total do vídeo: {format_hms(self.duration_seconds)}")
        lines.append(f"Valor original: {self.raw}")
        for label, seconds in self.candidates:
            lines.append(f"Possível interpretação ({label}): {format_hms(seconds)}")
        lines.append("")
        lines.append("Nenhum corte foi realizado para este registro.")
        return "\n".join(lines)


@dataclass(frozen=True)
class ParsedTimestamp:
    seconds: float
    raw: str
    adjusted: bool
    note: Optional[str]


def parse_timestamp(raw: str, duration_seconds: Optional[float] = None) -> ParsedTimestamp:
    text = raw.strip()
    parts = text.split(":")
    if len(parts) not in (2, 3, 4) or not all(p.isdigit() for p in parts):
        raise TimestampFormatError(f"Formato de timestamp não reconhecido: '{raw}'")

    numbers = [int(p) for p in parts]

    if len(numbers) == 2:
        minutes, seconds = numbers
        total = float(minutes * 60 + seconds)
        if duration_seconds is not None and total > duration_seconds:
            raise TimestampOutOfRangeError(raw, total, duration_seconds)
        return ParsedTimestamp(seconds=total, raw=raw, adjusted=False, note=None)

    if len(numbers) == 4:
        hours, minutes, seconds, extra = numbers
        if extra != 0:
            raise TimestampFormatError(
                f"Formato de timestamp não reconhecido: '{raw}' "
                "(quarto componente deveria ser '00')"
            )
        resolved = _resolve_three_parts(raw, hours, minutes, seconds, duration_seconds)
        note = "quarto componente ':00' descartado (artefato de planilha)"
        if resolved.note:
            note = f"{resolved.note}; {note}"
        return ParsedTimestamp(seconds=resolved.seconds, raw=raw, adjusted=True, note=note)

    hours, minutes, seconds = numbers
    return _resolve_three_parts(raw, hours, minutes, seconds, duration_seconds)


def _resolve_three_parts(
    raw: str, hours: int, minutes: int, seconds: int, duration_seconds: Optional[float]
) -> ParsedTimestamp:
    literal_seconds = float(hours * 3600 + minutes * 60 + seconds)

    if hours == 0 and minutes == 0 and seconds == 0:
        return ParsedTimestamp(seconds=0.0, raw=raw, adjusted=False, note=None)

    if seconds != 0:
        if duration_seconds is not None and literal_seconds > duration_seconds:
            raise TimestampOutOfRangeError(raw, literal_seconds, duration_seconds)
        return ParsedTimestamp(seconds=literal_seconds, raw=raw, adjusted=False, note=None)

    # Segundos == 0: pode ser H:MM:SS genuíno (ex.: "00:05:00" = 5 minutos,
    # bastante comum) ou MM:SS com um ":00" espúrio de planilha (ex.:
    # "29:07:00"). Só suspeitamos de corrupção quando a leitura literal
    # H:MM:SS não cabe na duração do vídeo — do contrário, confiamos nela.
    if duration_seconds is None:
        raise TimestampAmbiguousError(
            raw, None, [("H:MM:SS", literal_seconds), ("MM:SS", float(hours * 60 + minutes))]
        )

    if literal_seconds <= duration_seconds:
        return ParsedTimestamp(seconds=literal_seconds, raw=raw, adjusted=False, note=None)

    corrected_seconds = float(hours * 60 + minutes)
    if corrected_seconds <= duration_seconds:
        note = (
            f"'{raw}' interpretado como {format_hms(corrected_seconds)} "
            f"(leitura H:MM:SS de {format_hms(literal_seconds)} excederia a duração do vídeo)"
        )
        return ParsedTimestamp(seconds=corrected_seconds, raw=raw, adjusted=True, note=note)

    raise TimestampAmbiguousError(
        raw, duration_seconds, [("H:MM:SS", literal_seconds), ("MM:SS", corrected_seconds)]
    )


def format_hms(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def to_relative_seconds(absolute_seconds: float, cut_start_seconds: float) -> float:
    """Converte um timestamp absoluto (vídeo original) para relativo ao início do corte.

    Determinística, sem qualquer intervenção de IA (Feature_Editorializacao_Automatica.md
    seção 34) — a IA nunca decide um timestamp absoluto ou relativo em segundos, só
    propõe texto/posição relativa; esta função é sempre quem faz a conta.
    """
    return max(absolute_seconds - cut_start_seconds, 0.0)
