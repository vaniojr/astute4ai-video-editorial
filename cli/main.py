"""CLI do video-editorial (PRD seção 24)."""

import typer

from app.analysis import AnalysisError, DryRunReport, build_dry_run_report
from app.audio import AudioError, extract_audio
from app.config import load_settings
from app.downloader import DownloadError, download_video
from app.metadata import MetadataError
from app.project import (
    ProjectNotFoundError,
    advance_status,
    create_project,
    load_project,
    resolve_project_dir,
    update_status,
)
from app.timestamps import format_hms
from app.transcriber import TranscriptionError, transcribe_project

app = typer.Typer(help="Ferramenta local para produção editorial de vídeos.")


@app.callback()
def _callback() -> None:
    """video-editorial: ferramenta local para produção editorial de vídeos."""


@app.command()
def init(url: str = typer.Argument(..., help="URL do vídeo de origem (ex.: YouTube).")) -> None:
    """Cria um novo projeto a partir de uma URL de vídeo."""
    try:
        result = create_project(url)
    except MetadataError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if result.already_existed:
        typer.echo("Projeto já existente:\n")
        typer.echo(str(result.path))
        return

    project = result.project
    assert project is not None
    typer.echo("Projeto criado:\n")
    typer.echo(str(result.path))
    typer.echo("")
    typer.echo(f"Título: {project.title}")
    typer.echo(f"Canal: {project.channel or '(não detectado)'}")
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

    try:
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

    try:
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

    try:
        result = transcribe_project(project_dir, settings, force=force)
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
def cut(
    project: str = typer.Argument(..., help="Nome do diretório em projetos/ ou caminho do projeto."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Valida 03 Analise.csv e mostra os cortes elegíveis, sem gerar vídeos."
    ),
) -> None:
    """Gera os cortes definidos em 03 Analise.csv."""
    settings = load_settings()
    try:
        project_dir = resolve_project_dir(project, settings)
    except ProjectNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if not dry_run:
        typer.echo(
            "A geração real dos cortes ainda não está implementada nesta versão.\n\n"
            "Use 'video-editorial cut PROJECT --dry-run' para validar 03 Analise.csv "
            "e ver os cortes elegíveis.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        report = build_dry_run_report(project_dir)
    except AnalysisError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    _print_dry_run_report(report)
    advance_status(project_dir, "analyzed")


def _print_dry_run_report(report: DryRunReport) -> None:
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
        elif chapter.status == "ambiguous":
            typer.echo(f"[AMBÍGUO] Capítulo {chapter.row.capitulo}")
            typer.echo(chapter.message)
        elif chapter.status == "manual_action":
            typer.echo(f"[AVISO] Capítulo {chapter.row.capitulo}")
            typer.echo(chapter.message)
        elif chapter.status == "error":
            typer.echo(f"[ERRO] Capítulo {chapter.row.capitulo}")
            typer.echo(chapter.message)

    if report.warnings:
        typer.echo("")
        typer.echo("Avisos:")
        for warning in report.warnings:
            typer.echo(f"- {warning}")


if __name__ == "__main__":
    app()
