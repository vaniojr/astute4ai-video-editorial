"""Orquestração dos comandos `editorialize`/`render`.

`plan_editorial()`/`plan_render()` nunca chamam o provider de IA nem o
FFmpeg — usados por `--dry-run`, sem custo e sem exigir `ANTHROPIC_API_KEY`
nem `transcricao.json` além do estritamente necessário para cada um (mesmo
padrão de `app/analyzer.py::plan_analysis()`). A resolução de
capítulo/corte/marca é compartilhada entre planejamento e renderização
(`_resolve_chapter_cut_context`) — renderizar não deveria exigir a
transcrição, que só o planejamento (via IA) precisa.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from app.analysis import ChapterReport, build_dry_run_report, select_single_chapter
from app.brands import Brand, load_brand
from app.config import Settings
from app.cutter import CutterError, build_cut_filename
from app.editorial_models import ContextCard, Cta, EditorialPlan, Highlight, Intro, SourceAttribution
from app.editorial_planner import build_editorial_plan, extract_transcript_excerpt, format_transcript_excerpt
from app.editorial_provider import EditorialRequest, get_editorial_provider
from app.editorial_renderer import RenderResult, render_editorial_video
from app.logging_utils import log_operation
from app.project import Project, load_project
from app.transcriber import TranscriptSegment
from app.versioning import format_version, next_version_number

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "editorial"
_PLAN_GLOB = "editorial_plan_v*.json"


class EditorialServiceError(Exception):
    """Erro acionável na orquestração de editorialização (não específico de provider)."""


@dataclass(frozen=True)
class _ChapterCutContext:
    project: Project
    brand: Brand
    chapter_report: ChapterReport
    cut_path: Path
    editorial_dir: Path


def _resolve_chapter_cut_context(project_dir: Path, settings: Settings, *, chapter: int) -> _ChapterCutContext:
    project = load_project(project_dir)
    brand = load_brand(project.brand, settings.brands_dir)

    report = build_dry_run_report(project_dir)
    chapter_report = select_single_chapter(report.chapters, chapter=chapter)
    if chapter_report.status != "ok":
        raise EditorialServiceError(
            f"Capítulo {chapter} não está elegível para corte "
            f"(status={chapter_report.status}): {chapter_report.message or ''}"
        )

    try:
        cut_filename = build_cut_filename(chapter_report.row, settings)
    except CutterError as exc:
        raise EditorialServiceError(str(exc)) from exc

    cut_path = project_dir / "cortes" / cut_filename
    if not cut_path.is_file():
        raise EditorialServiceError(
            f"Corte não encontrado: {cut_path}\n\n"
            f"Rode 'video-editorial cut {project_dir.name} --chapter {chapter}' primeiro."
        )

    editorial_dir = project_dir / "editorial" / Path(cut_filename).stem

    return _ChapterCutContext(
        project=project, brand=brand, chapter_report=chapter_report, cut_path=cut_path, editorial_dir=editorial_dir
    )


# --- Planejamento (editorialize) -------------------------------------------------


@dataclass(frozen=True)
class EditorialGenerationPlan:
    project_dir: Path
    provider: str
    model: str
    project: Project
    brand: Brand
    chapter_report: ChapterReport
    cut_path: Path
    editorial_dir: Path
    cut_duration_seconds: float
    transcript_segments: List[TranscriptSegment]
    transcript_excerpt: str
    transcript_char_count: int
    already_exists: bool
    existing_plan_versions: int


def plan_editorial(
    project_dir: Path,
    settings: Settings,
    *,
    chapter: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> EditorialGenerationPlan:
    """Monta o plano de entrada sem chamar nenhum provider (usado por --dry-run)."""
    resolved_provider = provider or settings.editorial_provider
    resolved_model = model or settings.editorial_model

    context = _resolve_chapter_cut_context(project_dir, settings, chapter=chapter)

    transcricao_json_path = project_dir / "transcricao.json"
    if not transcricao_json_path.is_file():
        raise EditorialServiceError(
            f"Transcrição estruturada não encontrada: {transcricao_json_path}\n\n"
            "Execute 'video-editorial transcribe PROJECT' primeiro."
        )

    cut_duration_seconds = context.chapter_report.end_seconds - context.chapter_report.start_seconds
    transcript_segments = extract_transcript_excerpt(
        transcricao_json_path, context.chapter_report.start_seconds, context.chapter_report.end_seconds
    )
    transcript_excerpt = format_transcript_excerpt(transcript_segments)

    return EditorialGenerationPlan(
        project_dir=project_dir,
        provider=resolved_provider,
        model=resolved_model,
        project=context.project,
        brand=context.brand,
        chapter_report=context.chapter_report,
        cut_path=context.cut_path,
        editorial_dir=context.editorial_dir,
        cut_duration_seconds=cut_duration_seconds,
        transcript_segments=transcript_segments,
        transcript_excerpt=transcript_excerpt,
        transcript_char_count=len(transcript_excerpt),
        already_exists=(context.editorial_dir / "metadata.json").is_file(),
        existing_plan_versions=next_version_number(context.editorial_dir, _PLAN_GLOB) - 1,
    )


@dataclass(frozen=True)
class EditorialGenerationResult:
    plan: EditorialGenerationPlan
    skipped: bool
    editorial_plan: Optional[EditorialPlan] = None
    plan_path: Optional[Path] = None
    metadata_path: Optional[Path] = None


def generate_editorial(
    project_dir: Path,
    settings: Settings,
    *,
    chapter: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    force: bool = False,
) -> EditorialGenerationResult:
    plan = plan_editorial(project_dir, settings, chapter=chapter, provider=provider, model=model)

    if plan.already_exists and not force:
        return EditorialGenerationResult(plan=plan, skipped=True)

    comando = (
        f"editorialize {project_dir.name} --chapter={chapter} "
        f"--provider={plan.provider} --model={plan.model} --force={force}"
    )

    with log_operation(project_dir, etapa="editorialize", comando=comando) as log_extra:
        provider_instance = get_editorial_provider(
            plan.provider, model=plan.model, temperature=settings.editorial_temperature
        )
        request = EditorialRequest(
            tema_principal=plan.chapter_report.row.tema_principal,
            titulo_sugerido=plan.chapter_report.row.titulo_sugerido,
            resumo=plan.chapter_report.row.resumo,
            pergunta_principal=plan.chapter_report.row.pergunta_principal,
            trecho_para_validar_primeiro=plan.chapter_report.row.trecho_para_validar_primeiro,
            observacoes=plan.chapter_report.row.observacoes,
            transcript_excerpt=plan.transcript_excerpt,
            source_title=plan.project.title,
            source_channel=plan.project.channel or "",
            system_instructions=_load_prompt("system.md"),
            editorial_instructions=_load_prompt("editorial.md"),
        )
        result = provider_instance.plan(request)

        version = next_version_number(plan.editorial_dir, _PLAN_GLOB)
        editorial_plan = build_editorial_plan(
            result.candidate,
            chapter=plan.chapter_report.row.capitulo,
            cut_file=plan.cut_path.name,
            brand=plan.brand,
            project=plan.project,
            version=version,
            provider=result.provider,
            model=result.model,
            cut_duration_seconds=plan.cut_duration_seconds,
            transcript_segments=plan.transcript_segments,
        )

        plan.editorial_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan.editorial_dir / f"editorial_plan_{format_version(version)}.json"
        plan_path.write_text(
            json.dumps(asdict(editorial_plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        metadata_path = plan.editorial_dir / "metadata.json"
        metadata = {
            "chapter": editorial_plan.chapter,
            "cut_file": editorial_plan.cut_file,
            "provider": editorial_plan.provider,
            "model": editorial_plan.model,
            "latest_plan": plan_path.name,
            "status": "planned",
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        log_extra["provider"] = result.provider
        log_extra["model"] = result.model
        log_extra["input_tokens"] = result.usage.input_tokens if result.usage else None
        log_extra["output_tokens"] = result.usage.output_tokens if result.usage else None
        log_extra["cards"] = len(editorial_plan.context_cards)
        log_extra["highlights"] = len(editorial_plan.highlights)

    return EditorialGenerationResult(
        plan=plan, skipped=False, editorial_plan=editorial_plan, plan_path=plan_path, metadata_path=metadata_path
    )


# --- Renderização (render) --------------------------------------------------------


@dataclass(frozen=True)
class EditorialRenderPlan:
    project_dir: Path
    project: Project
    brand: Brand
    chapter_report: ChapterReport
    cut_path: Path
    editorial_dir: Path
    plan_version: int
    plan_path: Path
    editorial_plan: EditorialPlan
    output_path: Path
    already_exists: bool


def plan_render(
    project_dir: Path, settings: Settings, *, chapter: int, version: Optional[int] = None
) -> EditorialRenderPlan:
    """Monta o plano de renderização sem chamar o FFmpeg (usado por --dry-run).

    Não exige `transcricao.json` — renderizar só depende do plano
    editorial já gerado e do corte, nunca da transcrição em si.
    """
    context = _resolve_chapter_cut_context(project_dir, settings, chapter=chapter)

    existing_plan_versions = next_version_number(context.editorial_dir, _PLAN_GLOB) - 1
    resolved_version = version or existing_plan_versions
    if resolved_version <= 0:
        raise EditorialServiceError(
            f"Nenhum plano editorial encontrado para o capítulo {chapter}.\n\n"
            f"Rode 'video-editorial editorialize {project_dir.name} --chapter {chapter}' primeiro."
        )

    plan_path = context.editorial_dir / f"editorial_plan_{format_version(resolved_version)}.json"
    if not plan_path.is_file():
        raise EditorialServiceError(f"Versão {resolved_version} do plano não encontrada: {plan_path}")

    editorial_plan = _plan_from_dict(json.loads(plan_path.read_text(encoding="utf-8")))

    final_dir = project_dir / "final"
    slug = context.cut_path.stem
    final_glob = f"{slug}_v*.mp4"
    output_version = next_version_number(final_dir, final_glob)
    output_path = final_dir / f"{slug}_{format_version(output_version)}.mp4"

    return EditorialRenderPlan(
        project_dir=project_dir,
        project=context.project,
        brand=context.brand,
        chapter_report=context.chapter_report,
        cut_path=context.cut_path,
        editorial_dir=context.editorial_dir,
        plan_version=resolved_version,
        plan_path=plan_path,
        editorial_plan=editorial_plan,
        output_path=output_path,
        already_exists=output_version > 1,
    )


@dataclass(frozen=True)
class EditorialRenderGenerationResult:
    plan: EditorialRenderPlan
    skipped: bool
    render_result: Optional[RenderResult] = None


def render_editorial(
    project_dir: Path,
    settings: Settings,
    *,
    chapter: int,
    version: Optional[int] = None,
    force: bool = False,
) -> EditorialRenderGenerationResult:
    plan = plan_render(project_dir, settings, chapter=chapter, version=version)

    if plan.already_exists and not force:
        return EditorialRenderGenerationResult(plan=plan, skipped=True)

    comando = f"render {project_dir.name} --chapter={chapter} --version={plan.plan_version} --force={force}"

    with log_operation(project_dir, etapa="render", comando=comando) as log_extra:
        render_result = render_editorial_video(
            plan.editorial_plan, plan.cut_path, plan.brand, plan.output_path, settings
        )

        metadata_path = plan.editorial_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        metadata["final_file"] = render_result.output_path.name
        metadata["status"] = "rendered"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        log_extra["intro_included"] = render_result.intro_included
        log_extra["cta_included"] = render_result.cta_included
        if render_result.skipped_text_reason:
            log_extra["skipped_text_reason"] = render_result.skipped_text_reason

    return EditorialRenderGenerationResult(plan=plan, skipped=False, render_result=render_result)


def _plan_from_dict(data: dict) -> EditorialPlan:
    return EditorialPlan(
        chapter=data["chapter"],
        cut_file=data["cut_file"],
        brand=data["brand"],
        version=data["version"],
        intro=Intro(**data["intro"]),
        source_attribution=SourceAttribution(**data["source_attribution"]),
        lower_thirds=list(data.get("lower_thirds", [])),
        context_cards=[ContextCard(**c) for c in data.get("context_cards", [])],
        highlights=[Highlight(**h) for h in data.get("highlights", [])],
        cta=Cta(**data["cta"]),
        provider=data.get("provider", ""),
        model=data.get("model", ""),
    )


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
