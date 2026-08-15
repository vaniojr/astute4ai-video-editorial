"""CLI do video-editorial (PRD seção 24)."""

import time
from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from app.analysis import (
    AnalysisError,
    ChapterReport,
    DryRunReport,
    build_dry_run_report,
    filter_chapters,
)
from app.analyzer import AnalysisServiceError, analyze_project, plan_analysis
from app.audio import AudioError, extract_audio
from app.brands import BrandNotFoundError
from app.chapter_status import get_chapter_statuses
from app.config import load_settings
from app.cutter import CutRunResult, CutterError, generate_cuts
from app.downloader import DownloadError, download_video
from app.editorial_provider import EditorialProviderError
from app.editorial_renderer import EditorialRenderError
from app.editorial_service import (
    EditorialServiceError,
    generate_editorial,
    plan_editorial,
    plan_render,
    render_editorial,
)
from app.logging_utils import log_event, log_operation
from app.metadata import MetadataError
from app.project import (
    ProjectNotFoundError,
    advance_status,
    create_project,
    load_project,
    resolve_project_dir,
    update_status,
)
from app.thumbnail_frames import ThumbnailFramesError
from app.thumbnail_service import (
    ThumbnailServiceError,
    generate_thumbnail,
    plan_thumbnail,
    select_thumbnail_version,
)
from app.timestamps import format_hms
from app.transcriber import TranscriptionError, transcribe_project

app = typer.Typer(help="Ferramenta local para produção editorial de vídeos.")


class CutMode(str, Enum):
    precise = "precise"
    fast = "fast"


@app.callback()
def _callback() -> None:
    """video-editorial: ferramenta local para produção editorial de vídeos."""
    load_dotenv()


@app.command()
def init(
    url: str = typer.Argument(..., help="URL do vídeo de origem (ex.: YouTube)."),
    brand: Optional[str] = typer.Option(
        None,
        "--brand",
        help="Brand Profile do projeto (ex.: generic, bussola-politica). Padrão: configuração da aplicação.",
    ),
) -> None:
    """Cria um novo projeto a partir de uma URL de vídeo."""
    # Sem log_operation aqui: o diretório do projeto (onde logs/pipeline.log
    # mora) só existe DEPOIS que create_project() já terminou — não há onde
    # gravar um "iniciado" antes disso. Registra só o resultado final.
    settings = load_settings()
    start = time.monotonic()
    try:
        result = create_project(url, settings, brand=brand)
    except BrandNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)
    except MetadataError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    duracao = round(time.monotonic() - start, 1)

    if result.already_existed:
        log_event(
            result.path,
            etapa="init",
            comando=f"init {url}",
            resultado="ok",
            extra={"duracao_segundos": duracao},
        )
        typer.echo("Projeto já existente:\n")
        typer.echo(str(result.path))
        return

    project = result.project
    assert project is not None
    log_event(
        result.path,
        etapa="init",
        comando=f"init {url}",
        resultado="ok",
        extra={"duracao_segundos": duracao},
    )
    typer.echo("Projeto criado:\n")
    typer.echo(str(result.path))
    typer.echo("")
    typer.echo(f"Título: {project.title}")
    typer.echo(f"Canal: {project.channel or '(não detectado)'}")
    typer.echo(f"Brand: {project.brand}")
    if project.duration_seconds is not None:
        typer.echo(f"Duração: {project.duration_seconds} segundos")


@app.command()
def download(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    force: bool = typer.Option(False, "--force", help="Forçar novo download mesmo se o arquivo já existir."),
) -> None:
    """Baixa o vídeo original de um projeto já criado."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    proj = load_project(project_dir)

    typer.echo("Baixando vídeo...")
    try:
        with log_operation(project_dir, etapa="download", comando=f"download {project} --force={force}"):
            result = download_video(project_dir, proj.source_url, settings, force=force)
    except DownloadError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo("Arquivo original já existe.")
        typer.echo("Nenhum download realizado.")
        return

    update_status(project_dir, "downloaded")
    typer.echo("Download concluído:\n")
    typer.echo(str(result.path))


@app.command()
def audio(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    force: bool = typer.Option(False, "--force", help="Forçar nova extração mesmo se o arquivo já existir."),
) -> None:
    """Extrai o áudio (mono, 16 kHz, WAV) do vídeo original de um projeto."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    typer.echo("Extraindo áudio...")
    try:
        with log_operation(project_dir, etapa="audio", comando=f"audio {project} --force={force}"):
            result = extract_audio(project_dir, force=force)
    except AudioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo("Arquivo de áudio já existe.")
        typer.echo("Nenhuma extração realizada.")
        return

    update_status(project_dir, "audio_ready")
    typer.echo("Áudio extraído:\n")
    typer.echo(str(result.path))


@app.command()
def transcribe(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    force: bool = typer.Option(False, "--force", help="Forçar nova transcrição mesmo se já existir."),
) -> None:
    """Transcreve o áudio de um projeto, preservando timestamps."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    def _on_segment(segment) -> None:
        start = format_hms(segment.start_seconds)
        end = format_hms(segment.end_seconds)
        typer.echo(f"[{start} → {end}] transcrito")

    typer.echo("Transcrevendo áudio (pode demorar bastante para vídeos longos)...")
    try:
        with log_operation(project_dir, etapa="transcribe", comando=f"transcribe {project} --force={force}"):
            result = transcribe_project(project_dir, settings, force=force, on_segment=_on_segment)
    except TranscriptionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo("Transcrição já existe.")
        typer.echo("Nenhuma transcrição realizada.")
        return

    update_status(project_dir, "transcribed")
    typer.echo("Transcrição concluída:\n")
    typer.echo(str(result.md_path))


@app.command()
def analyze(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Provider de análise editorial (padrão: configuração)."
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Modelo do provider (padrão: configuração)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostra o plano da análise (provider, modelo, tamanho) sem chamar a API."
    ),
    force: bool = typer.Option(
        False, "--force", help="Gerar novamente mesmo se 03 Analise.csv já existir."
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Não pedir confirmação antes de chamar a API (uso em automação)."
    ),
) -> None:
    """Gera 03 Analise.csv automaticamente via LLM, a partir de 01 Fonte.md e 02 Transcricao.md."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        plan = plan_analysis(project_dir, settings, provider=provider, model=model)
    except AnalysisServiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if dry_run:
        _print_analysis_plan(plan)
        return

    if plan.already_exists and not force:
        typer.echo("A análise já existe para este projeto.")
        typer.echo("Use --force para gerar novamente.")
        return

    if plan.long_transcript_warning:
        typer.echo(plan.long_transcript_warning)
        typer.echo("")

    if not yes:
        typer.echo(f"Provider: {plan.provider}")
        typer.echo(f"Modelo: {plan.model}")
        typer.echo("A análise utilizará uma API externa e poderá gerar custos.")
        if not _confirm_yes_no("Continuar? [s/N] "):
            typer.echo("Cancelado.")
            raise typer.Exit(code=0)

    typer.echo(
        f"Chamando a API da Claude ({plan.provider}/{plan.model}) — pode levar de segundos a minutos..."
    )
    try:
        # analyze_project() já registra início/fim (com uso de tokens) em
        # logs/pipeline.log internamente — não duplicamos o log aqui.
        result = analyze_project(project_dir, settings, provider=provider, model=model, force=force)
    except AnalysisServiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo("A análise já existe para este projeto.")
        typer.echo("Use --force para gerar novamente.")
        return

    typer.echo("Análise concluída:\n")
    typer.echo(str(plan.csv_path))
    if result.usage:
        typer.echo(f"Tokens: {result.usage.input_tokens} entrada / {result.usage.output_tokens} saída")
    typer.echo("")

    if result.dry_run_report is not None:
        _print_dry_run_report(result.dry_run_report)
    else:
        typer.echo(
            "Não foi possível validar os capítulos automaticamente (vídeo original "
            "não encontrado). Rode 'video-editorial cut PROJECT --dry-run' depois de "
            "baixar o vídeo."
        )


@app.command()
def cut(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Valida 03 Analise.csv e mostra os cortes elegíveis, sem gerar vídeos."
    ),
    mode: CutMode = typer.Option(
        CutMode.precise, "--mode", help="'precise' (padrão, re-encoding) ou 'fast' (-c copy)."
    ),
    priority: Optional[str] = typer.Option(None, "--priority", help="Filtra por Prioridade (ex.: A)."),
    chapter: Optional[int] = typer.Option(None, "--chapter", help="Filtra por Capitulo."),
    order: Optional[int] = typer.Option(None, "--order", help="Filtra por Ordem Publicacao."),
) -> None:
    """Gera os cortes definidos em 03 Analise.csv."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        report = build_dry_run_report(project_dir)
    except AnalysisError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    filtered_chapters = filter_chapters(report.chapters, priority=priority, chapter=chapter, order=order)
    report = replace(report, chapters=filtered_chapters)

    comando = (
        f"cut {project} --dry-run={dry_run} --mode={mode.value} "
        f"--priority={priority} --chapter={chapter} --order={order}"
    )
    start = time.monotonic()

    if dry_run:
        _print_dry_run_report(report)
        advance_status(project_dir, "analyzed")
        duracao = round(time.monotonic() - start, 1)
        log_event(
            project_dir, etapa="cut", comando=comando, resultado="ok", extra={"duracao_segundos": duracao}
        )
        return

    if mode == CutMode.fast:
        typer.echo(
            "Modo rápido utiliza keyframes e pode não iniciar exatamente no timestamp editorial.\n"
        )

    def _on_progress(chapter: ChapterReport) -> None:
        typer.echo(f"Cortando: Capítulo {chapter.row.capitulo}...")

    # "iniciado" só é gravado a partir daqui: as etapas acima (ler o CSV,
    # aplicar filtros) já rodaram para montar o relatório e são rápidas —
    # o corte em si (FFmpeg) é a parte demorada que queremos rastrear.
    log_event(project_dir, etapa="cut", comando=comando, resultado="iniciado")
    try:
        cut_result = generate_cuts(
            report, project_dir, settings, mode=mode.value, on_progress=_on_progress
        )
    except CutterError as exc:
        duracao = round(time.monotonic() - start, 1)
        log_event(
            project_dir,
            etapa="cut",
            comando=comando,
            resultado="erro",
            erro=str(exc),
            extra={"duracao_segundos": duracao},
        )
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    _print_cut_report(report, cut_result)

    has_errors = any(outcome.status == "error" for outcome in cut_result.outcomes)
    duracao = round(time.monotonic() - start, 1)
    log_event(
        project_dir,
        etapa="cut",
        comando=comando,
        resultado="erro" if has_errors else "ok",
        erro="uma ou mais linhas falharam; ver relatório" if has_errors else None,
        extra={"duracao_segundos": duracao, "cortes_gerados": cut_result.cut_count},
    )

    if cut_result.cut_count > 0:
        advance_status(project_dir, "cut")


@app.command()
def editorialize(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    chapter: int = typer.Option(..., "--chapter", help="Número do capítulo (Capitulo no CSV)."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Provider de editorialização (padrão: configuração)."
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Modelo do provider (padrão: configuração)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostra o plano de entrada (trecho de transcrição, provider) sem chamar a API."
    ),
    force: bool = typer.Option(
        False, "--force", help="Gerar novamente mesmo se já existir um plano para este capítulo."
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Não pedir confirmação antes de chamar a API (uso em automação)."
    ),
) -> None:
    """Gera um plano editorial (intro, cards, destaques) para um capítulo, via LLM.

    Não renderiza vídeo nenhum — só produz `editorial_plan_vNNN.json` para revisão.
    """
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        plan = plan_editorial(project_dir, settings, chapter=chapter, provider=provider, model=model)
    except (EditorialServiceError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if dry_run:
        _print_editorial_plan(plan)
        return

    if plan.already_exists and not force:
        typer.echo(f"Já existe um plano editorial para o capítulo {chapter}.")
        typer.echo("Use --force para gerar novamente.")
        return

    if not yes:
        typer.echo(f"Provider: {plan.provider}")
        typer.echo(f"Modelo: {plan.model}")
        typer.echo("A editorialização utilizará uma API externa e poderá gerar custos.")
        if not _confirm_yes_no("Continuar? [s/N] "):
            typer.echo("Cancelado.")
            raise typer.Exit(code=0)

    typer.echo(f"Chamando a API da Claude ({plan.provider}/{plan.model})...")
    try:
        result = generate_editorial(
            project_dir, settings, chapter=chapter, provider=provider, model=model, force=force
        )
    except (EditorialServiceError, EditorialProviderError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo(f"Já existe um plano editorial para o capítulo {chapter}.")
        typer.echo("Use --force para gerar novamente.")
        return

    editorial_plan = result.editorial_plan
    typer.echo("Plano editorial gerado:\n")
    typer.echo(str(result.plan_path))
    typer.echo("")
    typer.echo(f"Intro: {'sim' if editorial_plan.intro.mode == 'text_only' else 'não'}")
    typer.echo(f"Cards: {len(editorial_plan.context_cards)}")
    typer.echo(f"Destaques: {len(editorial_plan.highlights)}")
    typer.echo(f"CTA: {'sim' if editorial_plan.cta.enabled else 'não'}")
    typer.echo("")
    typer.echo(
        f"Revise o plano e rode 'video-editorial render {project_dir.name} --chapter {chapter}' "
        "para gerar o vídeo final."
    )


@app.command()
def render(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    chapter: int = typer.Option(..., "--chapter", help="Número do capítulo (Capitulo no CSV)."),
    version: Optional[int] = typer.Option(
        None, "--version", help="Versão do plano editorial a renderizar (padrão: mais recente)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostra o que seria renderizado (intro/CTA/versão) sem chamar o FFmpeg."
    ),
    force: bool = typer.Option(
        False, "--force", help="Renderizar de novo mesmo se já existir um final/*.mp4 para este capítulo."
    ),
) -> None:
    """Renderiza o vídeo final (intro + corte + CTA) a partir de um plano editorial já gerado."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        plan = plan_render(project_dir, settings, chapter=chapter, version=version)
    except (EditorialServiceError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if dry_run:
        _print_render_plan(plan)
        return

    if plan.already_exists and not force:
        typer.echo(f"Já existe um vídeo final para o capítulo {chapter}.")
        typer.echo("Use --force para renderizar de novo (gera uma nova versão).")
        return

    typer.echo(f"Renderizando a partir do plano v{plan.plan_version:03d}...")
    try:
        result = render_editorial(project_dir, settings, chapter=chapter, version=version, force=force)
    except (EditorialServiceError, EditorialRenderError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo(f"Já existe um vídeo final para o capítulo {chapter}.")
        typer.echo("Use --force para renderizar de novo (gera uma nova versão).")
        return

    render_result = result.render_result
    typer.echo("Vídeo final gerado:\n")
    typer.echo(str(render_result.output_path))
    typer.echo("")
    typer.echo(f"Intro incluída: {'sim' if render_result.intro_included else 'não'}")
    typer.echo(f"CTA incluído: {'sim' if render_result.cta_included else 'não'}")
    if render_result.skipped_text_reason:
        typer.echo("")
        typer.echo(render_result.skipped_text_reason)


@app.command()
def thumbnail(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    chapter: int = typer.Option(..., "--chapter", help="Número do capítulo (Capitulo no CSV)."),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Provider de thumbnail (padrão: configuração). Só 'manual' disponível por enquanto.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostra o plano (frames candidatos, briefing previsto) sem gerar nada."
    ),
    force: bool = typer.Option(
        False, "--force", help="Gerar novamente mesmo se já existir frames/briefing para este capítulo."
    ),
) -> None:
    """Extrai frames reais do corte, gera o briefing editorial e (com um provider
    de imagem configurado) as thumbnails candidatas.

    Com `--provider manual` (padrão por enquanto), nenhuma imagem é gerada —
    só frames + briefing + opções de headline, prontos para uso manual.
    """
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        plan = plan_thumbnail(project_dir, settings, chapter=chapter, provider=provider)
    except (ThumbnailServiceError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if dry_run:
        _print_thumbnail_plan(plan)
        return

    if plan.already_exists and not force:
        typer.echo(f"Frames/briefing já existem para o capítulo {chapter}.")
        typer.echo("Use --force para gerar novamente.")
        return

    typer.echo(f"Extraindo {plan.frame_count} frames de '{plan.cut_path.name}'...")
    try:
        result = generate_thumbnail(
            project_dir, settings, chapter=chapter, provider=provider, force=force
        )
    except (ThumbnailServiceError, ThumbnailFramesError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.skipped:
        typer.echo(f"Frames/briefing já existem para o capítulo {chapter}.")
        typer.echo("Use --force para gerar novamente.")
        return

    typer.echo("Concluído:\n")
    typer.echo(str(plan.thumb_dir))
    typer.echo(f"- {len(result.frame_paths)} frame(s) em frames/")
    typer.echo("- briefing.md")
    typer.echo("- metadata.json")
    if result.image_paths:
        typer.echo(f"- {len(result.image_paths)} thumbnail(s) gerada(s):")
        for image_path in result.image_paths:
            typer.echo(f"  {image_path.name}")
        typer.echo("")
        typer.echo(
            f"Use 'video-editorial thumbnail-select {project_dir.name} --chapter {chapter} "
            "--version N' para aprovar uma versão."
        )
    else:
        typer.echo("")
        typer.echo(f"Nenhuma imagem gerada — provider '{plan.provider}' configurado.")
        typer.echo("Frames e briefing estão prontos para uso manual.")


@app.command(name="thumbnail-select")
def thumbnail_select(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    chapter: int = typer.Option(..., "--chapter", help="Número do capítulo (Capitulo no CSV)."),
    version: int = typer.Option(..., "--version", help="Número da versão gerada (ex.: 2 para thumbnail_v002.png)."),
) -> None:
    """Marca uma versão da thumbnail gerada como aprovada (grava thumbs/.../selected.png)."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        result = select_thumbnail_version(project_dir, settings, chapter=chapter, version=version)
    except (ThumbnailServiceError, AnalysisError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Thumbnail v{version:03d} selecionada para o capítulo {chapter}:")
    typer.echo(str(result.selected_path))


@app.command()
def status(
    project: str = typer.Argument(
        ..., help="Nome do diretório em projetos/, caminho, ou source_id do vídeo."
    ),
) -> None:
    """Mostra o estado atual de um projeto e a presença dos artefatos do pipeline."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    proj = load_project(project_dir)

    typer.echo("Projeto:")
    typer.echo(project_dir.name)
    typer.echo("")
    typer.echo(f"Título: {proj.title}")
    typer.echo(f"Canal: {proj.channel or '(não detectado)'}")
    typer.echo(f"URL: {proj.source_url}")
    typer.echo(f"Brand: {proj.brand}")
    typer.echo(f"Status: {proj.status}")
    typer.echo("")
    typer.echo("Artefatos:")
    typer.echo(f"- Vídeo original: {_presence(project_dir / 'original' / 'video-original.mp4')}")
    typer.echo(f"- Áudio: {_presence(project_dir / 'audio' / 'audio.wav')}")
    typer.echo(f"- Transcrição: {_presence(project_dir / '02 Transcricao.md')}")
    typer.echo(f"- Análise (03 Analise.csv): {_presence(project_dir / '03 Analise.csv')}")
    cortes_dir = project_dir / "cortes"
    cortes_count = len(list(cortes_dir.glob("*.mp4"))) if cortes_dir.is_dir() else 0
    typer.echo(f"- Cortes: {cortes_count} arquivo(s) em cortes/")

    chapter_statuses = get_chapter_statuses(project_dir, settings)
    if chapter_statuses:
        typer.echo("")
        typer.echo("Por capítulo:")
        for chapter in chapter_statuses:
            cut_marca = "✓" if chapter.cut else "✗"
            editorial_marca = "✓" if chapter.editorial_planned else "✗"
            typer.echo(
                f"- Capítulo {chapter.capitulo}: cut {cut_marca} | editorial (planejado) {editorial_marca}"
            )


def _presence(path: Path) -> str:
    return "presente" if path.exists() else "ausente"


def _print_analysis_plan(plan) -> None:
    typer.echo("Projeto:")
    typer.echo(plan.project_dir.name)
    typer.echo("")
    typer.echo("Provider:")
    typer.echo(plan.provider)
    typer.echo("")
    typer.echo("Modelo:")
    typer.echo(plan.model)
    typer.echo("")
    typer.echo("Fonte:")
    typer.echo(plan.source_path.name)
    typer.echo("")
    typer.echo("Transcrição:")
    typer.echo(plan.transcript_path.name)
    typer.echo("")
    typer.echo("Caracteres:")
    typer.echo(f"{plan.transcript_char_count:,}".replace(",", "."))
    typer.echo("")
    typer.echo("Saída:")
    typer.echo(plan.csv_path.name)
    if plan.long_transcript_warning:
        typer.echo("")
        typer.echo(plan.long_transcript_warning)
    typer.echo("")
    typer.echo("DRY RUN")
    typer.echo("Nenhuma chamada de API realizada.")


def _print_thumbnail_plan(plan) -> None:
    row = plan.chapter_report.row
    typer.echo("Projeto:")
    typer.echo(plan.project_dir.name)
    typer.echo("Capítulo:")
    typer.echo(row.capitulo)
    typer.echo("Intervalo:")
    typer.echo(f"{format_hms(plan.chapter_report.start_seconds)} → {format_hms(plan.chapter_report.end_seconds)}")
    typer.echo("Tema:")
    typer.echo(row.tema_principal or "(não informado)")
    typer.echo("Brand:")
    typer.echo(plan.brand.name)
    typer.echo("Frames candidatos:")
    typer.echo(str(plan.frame_count))
    typer.echo("Thumbnail:")
    typer.echo(f"{plan.brand.thumbnail.width}x{plan.brand.thumbnail.height}")
    typer.echo("Provider:")
    typer.echo(plan.provider)
    typer.echo("Versões existentes:")
    typer.echo(str(plan.existing_image_versions))
    typer.echo("")
    typer.echo("DRY RUN")
    typer.echo("Nenhuma imagem final será gerada.")


def _print_editorial_plan(plan) -> None:
    row = plan.chapter_report.row
    typer.echo("Projeto:")
    typer.echo(plan.project_dir.name)
    typer.echo("Capítulo:")
    typer.echo(row.capitulo)
    typer.echo("Corte:")
    typer.echo(plan.cut_path.name)
    typer.echo("Tema:")
    typer.echo(row.tema_principal or "(não informado)")
    typer.echo("Brand:")
    typer.echo(plan.brand.name)
    typer.echo("Provider:")
    typer.echo(plan.provider)
    typer.echo("Modelo:")
    typer.echo(plan.model)
    typer.echo("Trecho de transcrição enviado:")
    typer.echo(f"{plan.transcript_char_count:,}".replace(",", ".") + " caracteres")
    typer.echo("Versões de plano existentes:")
    typer.echo(str(plan.existing_plan_versions))
    typer.echo("")
    typer.echo("DRY RUN")
    typer.echo("Nenhuma chamada de API realizada.")


def _print_render_plan(plan) -> None:
    editorial_plan = plan.editorial_plan
    typer.echo("Projeto:")
    typer.echo(plan.project_dir.name)
    typer.echo("Capítulo:")
    typer.echo(str(editorial_plan.chapter))
    typer.echo("Corte:")
    typer.echo(plan.cut_path.name)
    typer.echo("Plano:")
    typer.echo(f"v{plan.plan_version:03d} ({plan.plan_path.name})")
    typer.echo("Intro:")
    typer.echo("sim" if editorial_plan.intro.mode == "text_only" else "não")
    typer.echo("CTA:")
    typer.echo("sim" if editorial_plan.cta.enabled else "não")
    typer.echo("Fonte da marca configurada:")
    font = plan.brand.assets.primary_font
    typer.echo("sim" if font and font.is_file() else "não (intro/CTA em texto seriam pulados)")
    typer.echo("Arquivo final previsto:")
    typer.echo(plan.output_path.name)
    typer.echo("")
    typer.echo("DRY RUN")
    typer.echo("Nenhum vídeo será gerado.")


def _confirm_yes_no(prompt: str) -> bool:
    response = input(prompt)
    return response.strip().lower() == "s"


def _print_dry_run_report(report: DryRunReport) -> None:
    _print_report_header(report)
    typer.echo("Cortes elegíveis:")
    typer.echo(str(report.eligible_count))

    for chapter in report.chapters:
        if chapter.status == "discarded":
            continue
        typer.echo("")
        if chapter.status == "ok":
            suffix = " (timestamp ajustado)" if chapter.message else ""
            typer.echo(f"[OK] Capítulo {chapter.row.capitulo}{suffix}")
            typer.echo(f"{format_hms(chapter.start_seconds)} → {format_hms(chapter.end_seconds)}")
            typer.echo(f"Duração: {format_hms(chapter.end_seconds - chapter.start_seconds)}")
            if chapter.message:
                typer.echo(f"Nota: {chapter.message}")
        else:
            _print_ineligible_chapter(chapter)

    _print_warnings(report)


def _print_cut_report(report: DryRunReport, cut_result: CutRunResult) -> None:
    _print_report_header(report)
    typer.echo("Cortes gerados:")
    typer.echo(str(cut_result.cut_count))

    for outcome in cut_result.outcomes:
        chapter = outcome.chapter
        if outcome.status == "skipped_ineligible" and chapter.status == "discarded":
            continue
        typer.echo("")
        if outcome.status == "cut":
            typer.echo(f"[CORTADO] Capítulo {chapter.row.capitulo}")
            typer.echo(outcome.output_path.name)
        elif outcome.status == "skipped_exists":
            typer.echo(f"[PULADO] Capítulo {chapter.row.capitulo} (arquivo já existe)")
            typer.echo(outcome.output_path.name)
        elif outcome.status == "error":
            typer.echo(f"[ERRO] Capítulo {chapter.row.capitulo}")
            typer.echo(outcome.message)
        else:  # skipped_ineligible (ambíguo/aviso/erro de validação)
            _print_ineligible_chapter(chapter)

    _print_warnings(report)


def _print_report_header(report: DryRunReport) -> None:
    typer.echo("Projeto:")
    typer.echo(report.project_dir.name)
    typer.echo("")
    typer.echo("Vídeo:")
    typer.echo(str(report.video_path.relative_to(report.project_dir)))
    typer.echo("")
    typer.echo("Duração:")
    typer.echo(format_hms(report.video_duration_seconds))
    typer.echo("")
    typer.echo("CSV:")
    typer.echo(report.csv_path.name)
    typer.echo("")


def _print_ineligible_chapter(chapter: ChapterReport) -> None:
    if chapter.status == "ambiguous":
        typer.echo(f"[AMBÍGUO] Capítulo {chapter.row.capitulo}")
        typer.echo(chapter.message)
    elif chapter.status == "manual_action":
        typer.echo(f"[AVISO] Capítulo {chapter.row.capitulo}")
        typer.echo(chapter.message)
    elif chapter.status == "error":
        typer.echo(f"[ERRO] Capítulo {chapter.row.capitulo}")
        typer.echo(chapter.message)


def _print_warnings(report: DryRunReport) -> None:
    if report.warnings:
        typer.echo("")
        typer.echo("Avisos:")
        for warning in report.warnings:
            typer.echo(f"- {warning}")


if __name__ == "__main__":
    app()
