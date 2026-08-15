"""Leitura, validação e dry-run de `03 Analise.csv` (PRD seções 14–18).

A análise editorial em si continua sendo produzida externamente (Claude no
VS Code, manualmente) — este módulo só lê o CSV já existente, valida
timestamps/ações editoriais e monta o relatório de dry-run. A geração real
dos cortes (FFmpeg) fica para `app/cutter.py`, na Entrega 6.
"""

import csv
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.timestamps import (
    TimestampAmbiguousError,
    TimestampFormatError,
    TimestampOutOfRangeError,
    format_hms,
    parse_timestamp,
)

_CSV_FILENAME = "03 Analise.csv"

_REQUIRED_COLUMNS = (
    "Ordem Publicacao",
    "Capitulo",
    "Acao Editorial",
    "Timestamp Inicial",
    "Timestamp Final",
)

_COLUMN_TO_FIELD = {
    "Ordem Publicacao": "ordem_publicacao",
    "Prioridade": "prioridade",
    "Capitulo": "capitulo",
    "Bloco Editorial": "bloco_editorial",
    "Acao Editorial": "acao_editorial",
    "Timestamp Inicial": "timestamp_inicial",
    "Timestamp Final": "timestamp_final",
    "Duracao": "duracao",
    "Tema Principal": "tema_principal",
    "Titulo Sugerido": "titulo_sugerido",
    "Palavra-chave Principal": "palavra_chave_principal",
    "Trecho para Validar Primeiro": "trecho_para_validar_primeiro",
    "Resumo": "resumo",
    "Pergunta Principal": "pergunta_principal",
    "Independente": "independente",
    "Precisa Contexto Anterior": "precisa_contexto_anterior",
    "Grau de Confianca": "grau_de_confianca",
    "Observacoes": "observacoes",
}

_KEEP_ACTIONS = {"manter"}
_DISCARD_ACTIONS = {"descartar", "nao publicar", "arquivar"}
_MANUAL_ACTIONS = {"unir", "separar", "transformar em teaser", "revisar"}

_DURATION_TOLERANCE_SECONDS = 1.0


class AnalysisError(Exception):
    """Erro acionável ao ler ou validar 03 Analise.csv."""


@dataclass(frozen=True)
class AnalysisRow:
    ordem_publicacao: str = ""
    prioridade: str = ""
    capitulo: str = ""
    bloco_editorial: str = ""
    acao_editorial: str = ""
    timestamp_inicial: str = ""
    timestamp_final: str = ""
    duracao: str = ""
    tema_principal: str = ""
    titulo_sugerido: str = ""
    palavra_chave_principal: str = ""
    trecho_para_validar_primeiro: str = ""
    resumo: str = ""
    pergunta_principal: str = ""
    independente: str = ""
    precisa_contexto_anterior: str = ""
    grau_de_confianca: str = ""
    observacoes: str = ""


def load_analysis(csv_path: Path) -> List[AnalysisRow]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        missing = [col for col in _REQUIRED_COLUMNS if col not in fieldnames]
        if missing:
            raise AnalysisError(
                "03 Analise.csv está sem colunas obrigatórias.\n\n"
                f"Faltando: {', '.join(missing)}\n\n"
                f"Colunas encontradas: {', '.join(fieldnames) or '(nenhuma)'}"
            )

        rows = []
        for raw_row in reader:
            kwargs = {}
            for column, field_name in _COLUMN_TO_FIELD.items():
                kwargs[field_name] = (raw_row.get(column) or "").strip()
            rows.append(AnalysisRow(**kwargs))
        return rows


def classify_action(raw_action: str) -> str:
    normalized = _normalize(raw_action)
    if normalized in _KEEP_ACTIONS:
        return "keep"
    if normalized in _DISCARD_ACTIONS:
        return "discard"
    if normalized in _MANUAL_ACTIONS:
        return "manual"
    return "unknown"


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class ChapterReport:
    row: AnalysisRow
    status: str  # "ok" | "ambiguous" | "manual_action" | "error"
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class DryRunReport:
    project_dir: Path
    video_path: Path
    video_duration_seconds: float
    csv_path: Path
    chapters: List[ChapterReport] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def eligible_count(self) -> int:
        return sum(1 for chapter in self.chapters if chapter.status == "ok")


def filter_chapters(
    chapters: List[ChapterReport],
    *,
    priority: Optional[str] = None,
    chapter: Optional[int] = None,
    order: Optional[int] = None,
) -> List[ChapterReport]:
    """Filtra capítulos por Prioridade/Capitulo/Ordem Publicacao (PRD seção 19).

    Filtros combinam em AND quando mais de um é informado. `None` desativa
    o respectivo filtro.
    """
    result = chapters
    if priority is not None:
        normalized = priority.strip().lower()
        result = [c for c in result if c.row.prioridade.strip().lower() == normalized]
    if chapter is not None:
        result = [c for c in result if _safe_int(c.row.capitulo) == chapter]
    if order is not None:
        result = [c for c in result if _safe_int(c.row.ordem_publicacao) == order]
    return result


def _safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_dry_run_report(project_dir: Path) -> DryRunReport:
    video_path = project_dir / "original" / "video-original.mp4"
    if not video_path.exists():
        raise AnalysisError(
            "Vídeo original não encontrado.\n\n"
            f"Esperado em: {video_path}\n\n"
            "Execute 'video-editorial download PROJECT' primeiro."
        )

    csv_path = project_dir / _CSV_FILENAME
    if not csv_path.exists():
        raise AnalysisError(
            "Análise editorial não encontrada.\n\n"
            f"Esperado em: {csv_path}\n\n"
            "A análise editorial ainda é produzida externamente (ver PRD seção 14). "
            "Gere-a e salve nesse caminho antes de rodar o dry-run."
        )

    video_duration = _get_video_duration_seconds(video_path)
    rows = load_analysis(csv_path)

    chapters = [_evaluate_row(row, video_duration) for row in rows]
    warnings = _cross_row_warnings(chapters)

    return DryRunReport(
        project_dir=project_dir,
        video_path=video_path,
        video_duration_seconds=video_duration,
        csv_path=csv_path,
        chapters=chapters,
        warnings=warnings,
    )


def _evaluate_row(row: AnalysisRow, video_duration_seconds: float) -> ChapterReport:
    action = classify_action(row.acao_editorial)

    if action == "discard":
        return ChapterReport(row=row, status="discarded")
    if action == "manual":
        return ChapterReport(
            row=row,
            status="manual_action",
            message=(
                f"Ação '{row.acao_editorial}' requer edição manual, "
                "não suportada automaticamente nesta versão."
            ),
        )
    if action == "unknown":
        return ChapterReport(
            row=row, status="error", message=f"Ação editorial desconhecida: '{row.acao_editorial}'"
        )

    try:
        start = parse_timestamp(row.timestamp_inicial, video_duration_seconds)
        end = parse_timestamp(row.timestamp_final, video_duration_seconds)
    except (TimestampFormatError, TimestampOutOfRangeError) as exc:
        return ChapterReport(row=row, status="error", message=str(exc))
    except TimestampAmbiguousError as exc:
        return ChapterReport(row=row, status="ambiguous", message=str(exc))

    if end.seconds <= start.seconds:
        return ChapterReport(
            row=row,
            status="error",
            message=(
                f"Timestamp final ({row.timestamp_final}) não é maior que o "
                f"inicial ({row.timestamp_inicial})."
            ),
        )

    computed_duration = end.seconds - start.seconds

    if row.duracao:
        try:
            declared = parse_timestamp(row.duracao, video_duration_seconds)
        except (TimestampFormatError, TimestampOutOfRangeError, TimestampAmbiguousError) as exc:
            return ChapterReport(
                row=row,
                status="error",
                message=f"Coluna Duracao inválida ('{row.duracao}'): {exc}",
            )
        if abs(declared.seconds - computed_duration) > _DURATION_TOLERANCE_SECONDS:
            return ChapterReport(
                row=row,
                status="error",
                message=(
                    f"Duração declarada ({row.duracao} = {format_hms(declared.seconds)}) não "
                    f"confere com o intervalo do timestamp ({format_hms(computed_duration)})."
                ),
            )

    notes = [note for note in (start.note, end.note) if note]
    message = "; ".join(notes) if notes else None

    return ChapterReport(
        row=row, status="ok", start_seconds=start.seconds, end_seconds=end.seconds, message=message
    )


def _cross_row_warnings(chapters: List[ChapterReport]) -> List[str]:
    warnings: List[str] = []
    ok_chapters = [c for c in chapters if c.status == "ok"]

    seen_chapters = {}
    for chapter in ok_chapters:
        capitulo = chapter.row.capitulo
        seen_chapters.setdefault(capitulo, []).append(chapter)
    for capitulo, group in seen_chapters.items():
        if len(group) > 1:
            warnings.append(f"Capítulo duplicado: '{capitulo}' aparece em {len(group)} registros elegíveis.")

    for i, a in enumerate(ok_chapters):
        for b in ok_chapters[i + 1 :]:
            if a.start_seconds < b.end_seconds and b.start_seconds < a.end_seconds:
                warnings.append(
                    f"Sobreposição entre Capítulo '{a.row.capitulo}' "
                    f"({format_hms(a.start_seconds)} → {format_hms(a.end_seconds)}) e "
                    f"Capítulo '{b.row.capitulo}' "
                    f"({format_hms(b.start_seconds)} → {format_hms(b.end_seconds)})."
                )

    return warnings


def _get_video_duration_seconds(video_path: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise AnalysisError(
            "FFmpeg não foi encontrado.\n\n"
            "Instale no macOS:\n\n"
            "brew install ffmpeg"
        )

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnalysisError(
            "Não foi possível obter a duração do vídeo original com ffprobe.\n\n"
            f"{result.stderr.strip()}"
        )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise AnalysisError(
            f"ffprobe retornou uma duração inválida para {video_path}: '{result.stdout.strip()}'"
        ) from exc
