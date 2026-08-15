"""Orquestração dos comandos `thumbnail`/`thumbnail-select`.

Frames + briefing + headlines funcionam integralmente sem nenhuma API paga
(`--provider manual`, único disponível por enquanto — `app/thumbnail_provider.py`
nunca importa SDK de nenhum provider real). Quando um provider real gerar
imagens, este módulo é quem aplica versionamento (`app/versioning.py`) e
grava os arquivos — o provider só devolve bytes, nunca decide nome de
arquivo (mesma separação que `app/cutter.py` já usa para os cortes).
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.analysis import AnalysisError, ChapterReport, build_dry_run_report, select_single_chapter
from app.brands import Brand, load_brand
from app.config import Settings
from app.cutter import CutterError, build_cut_filename
from app.logging_utils import log_operation
from app.project import Project, load_project
from app.thumbnail_briefing import build_briefing, build_headline_options
from app.thumbnail_frames import FRAME_COUNT, extract_frames
from app.thumbnail_provider import (
    ThumbnailProviderError,
    ThumbnailRequest,
    get_thumbnail_provider,
)
from app.versioning import format_version, next_version_number

_IMAGE_GLOB = "thumbnail_v*.png"


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
    existing_image_versions: int


def plan_thumbnail(
    project_dir: Path, settings: Settings, *, chapter: int, provider: Optional[str] = None
) -> ThumbnailPlan:
    """Monta o plano do thumbnail sem extrair nenhum frame nem chamar provider (usado por --dry-run)."""
    resolved_provider = provider or settings.thumbnail_provider
    try:
        get_thumbnail_provider(resolved_provider)
    except ThumbnailProviderError as exc:
        raise ThumbnailServiceError(str(exc)) from exc

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
        existing_image_versions=next_version_number(thumb_dir, _IMAGE_GLOB) - 1,
    )


@dataclass(frozen=True)
class ThumbnailGenerationResult:
    plan: ThumbnailPlan
    skipped: bool
    frame_paths: Optional[List[Path]] = None
    briefing_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    image_paths: Optional[List[Path]] = None


def generate_thumbnail(
    project_dir: Path,
    settings: Settings,
    *,
    chapter: int,
    provider: Optional[str] = None,
    force: bool = False,
) -> ThumbnailGenerationResult:
    plan = plan_thumbnail(project_dir, settings, chapter=chapter, provider=provider)

    if plan.already_exists and not force:
        return ThumbnailGenerationResult(plan=plan, skipped=True)

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

        headline_options = build_headline_options(row)

        provider_instance = get_thumbnail_provider(plan.provider)
        thumbnail_request = ThumbnailRequest(
            reference_images=frame_paths,
            briefing=briefing_text,
            aspect_ratio="16:9",
            brand=plan.brand,
        )
        provider_result = provider_instance.generate(thumbnail_request)

        image_paths = []
        for image in provider_result.images:
            version = next_version_number(plan.thumb_dir, _IMAGE_GLOB)
            image_path = plan.thumb_dir / f"thumbnail_{format_version(version)}.png"
            image_path.write_bytes(image.content)
            image_paths.append(image_path)

        metadata = {
            "chapter": row.capitulo,
            "order": row.ordem_publicacao,
            "cut_file": plan.cut_path.name,
            "frames": [f"frames/{path.name}" for path in frame_paths],
            "headline": headline_options[0] if headline_options else "",
            "headline_options": headline_options,
            "participants_unknown": True,
            "provider": plan.provider,
            "images": [path.name for path in image_paths],
            "selected": None,
            "status": "generated" if image_paths else "briefing_ready",
        }
        metadata_path = plan.thumb_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        log_extra["frame_count"] = len(frame_paths)
        log_extra["images_generated"] = len(image_paths)

    return ThumbnailGenerationResult(
        plan=plan,
        skipped=False,
        frame_paths=frame_paths,
        briefing_path=briefing_path,
        metadata_path=metadata_path,
        image_paths=image_paths,
    )


@dataclass(frozen=True)
class ThumbnailSelectionResult:
    thumb_dir: Path
    selected_path: Path
    version: int


def select_thumbnail_version(
    project_dir: Path, settings: Settings, *, chapter: int, version: int
) -> ThumbnailSelectionResult:
    plan = plan_thumbnail(project_dir, settings, chapter=chapter)

    candidate = plan.thumb_dir / f"thumbnail_{format_version(version)}.png"
    if not candidate.is_file():
        raise ThumbnailServiceError(
            f"Versão {version} não encontrada: {candidate}\n\n"
            f"Rode 'video-editorial thumbnail {project_dir.name} --chapter {chapter}' "
            "com um provider de imagem configurado, ou confira quais versões existem em "
            f"'{plan.thumb_dir}'."
        )

    comando = f"thumbnail-select {project_dir.name} --chapter={chapter} --version={version}"
    with log_operation(project_dir, etapa="thumbnail-select", comando=comando):
        selected_path = plan.thumb_dir / "selected.png"
        shutil.copyfile(candidate, selected_path)

        metadata_path = plan.thumb_dir / "metadata.json"
        metadata = (
            json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        )
        metadata["selected"] = candidate.name
        metadata["status"] = "selected"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return ThumbnailSelectionResult(thumb_dir=plan.thumb_dir, selected_path=selected_path, version=version)
