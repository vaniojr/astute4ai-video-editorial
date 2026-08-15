"""Orquestração do comando `thumbnail` — Fase 9.1 (frames + briefing, modo manual).

Sem provider de geração de imagem ainda (fica para uma entrega futura).
`--provider` só aceita "manual" por enquanto — a superfície da CLI já fica
estável para quando o provider real entrar, sem precisar de uma nova flag
depois. `ThumbnailProvider` (ABC/factory) não existe ainda: com um único
caminho de código, essa abstração seria prematura.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.analysis import AnalysisError, ChapterReport, build_dry_run_report, select_single_chapter
from app.brands import Brand, load_brand
from app.config import Settings
from app.cutter import CutterError, build_cut_filename
from app.logging_utils import log_operation
from app.project import Project, load_project
from app.thumbnail_briefing import build_briefing
from app.thumbnail_frames import FRAME_COUNT, extract_frames

_SUPPORTED_PROVIDERS = ("manual",)


class ThumbnailServiceError(Exception):
    """Erro acionável na orquestração de thumbnail (não específico de provider/frames)."""


@dataclass(frozen=True)
class ThumbnailPlan:
    project_dir: Path
    provider: str
    project: Project
    brand: Brand
    chapter_report: ChapterReport
    cut_path: Path
    thumb_dir: Path
    frame_count: int
    already_exists: bool


def plan_thumbnail(
    project_dir: Path, settings: Settings, *, chapter: int, provider: Optional[str] = None
) -> ThumbnailPlan:
    """Monta o plano do thumbnail sem extrair nenhum frame (usado por --dry-run)."""
    resolved_provider = provider or settings.thumbnail_provider
    if resolved_provider not in _SUPPORTED_PROVIDERS:
        raise ThumbnailServiceError(
            f"Provider de thumbnail '{resolved_provider}' ainda não implementado. "
            f"Disponíveis: {', '.join(_SUPPORTED_PROVIDERS)}."
        )

    project = load_project(project_dir)
    brand = load_brand(project.brand, settings.brands_dir)

    report = build_dry_run_report(project_dir)
    chapter_report = select_single_chapter(report.chapters, chapter=chapter)
    if chapter_report.status != "ok":
        raise ThumbnailServiceError(
            f"Capítulo {chapter} não está elegível para corte "
            f"(status={chapter_report.status}): {chapter_report.message or ''}"
        )

    try:
        cut_filename = build_cut_filename(chapter_report.row, settings)
    except CutterError as exc:
        raise ThumbnailServiceError(str(exc)) from exc

    cut_path = project_dir / "cortes" / cut_filename
    if not cut_path.is_file():
        raise ThumbnailServiceError(
            f"Corte não encontrado: {cut_path}\n\n"
            f"Rode 'video-editorial cut {project_dir.name} --chapter {chapter}' primeiro."
        )

    thumb_dir = project_dir / "thumbs" / Path(cut_filename).stem

    return ThumbnailPlan(
        project_dir=project_dir,
        provider=resolved_provider,
        project=project,
        brand=brand,
        chapter_report=chapter_report,
        cut_path=cut_path,
        thumb_dir=thumb_dir,
        frame_count=FRAME_COUNT,
        already_exists=(thumb_dir / "metadata.json").is_file(),
    )


@dataclass(frozen=True)
class ThumbnailBriefingResult:
    plan: ThumbnailPlan
    skipped: bool
    frame_paths: Optional[List[Path]] = None
    briefing_path: Optional[Path] = None
    metadata_path: Optional[Path] = None


def generate_thumbnail_briefing(
    project_dir: Path,
    settings: Settings,
    *,
    chapter: int,
    provider: Optional[str] = None,
    force: bool = False,
) -> ThumbnailBriefingResult:
    plan = plan_thumbnail(project_dir, settings, chapter=chapter, provider=provider)

    if plan.already_exists and not force:
        return ThumbnailBriefingResult(plan=plan, skipped=True)

    comando = (
        f"thumbnail {project_dir.name} --chapter={chapter} --provider={plan.provider} --force={force}"
    )

    with log_operation(project_dir, etapa="thumbnail", comando=comando) as log_extra:
        row = plan.chapter_report.row
        duration = plan.chapter_report.end_seconds - plan.chapter_report.start_seconds

        frame_paths = extract_frames(plan.cut_path, plan.thumb_dir / "frames", duration)

        briefing_text = build_briefing(row, plan.project, plan.brand)
        briefing_path = plan.thumb_dir / "briefing.md"
        briefing_path.write_text(briefing_text, encoding="utf-8")

        metadata = {
            "chapter": row.capitulo,
            "order": row.ordem_publicacao,
            "cut_file": plan.cut_path.name,
            "frames": [f"frames/{path.name}" for path in frame_paths],
            "headline": row.titulo_sugerido,
            "participants_unknown": True,
            "provider": plan.provider,
            "status": "briefing_ready",
        }
        metadata_path = plan.thumb_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        log_extra["frame_count"] = len(frame_paths)

    return ThumbnailBriefingResult(
        plan=plan,
        skipped=False,
        frame_paths=frame_paths,
        briefing_path=briefing_path,
        metadata_path=metadata_path,
    )
