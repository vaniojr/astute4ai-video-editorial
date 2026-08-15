"""CLI do video-editorial (PRD seção 24)."""

import typer

from app.audio import AudioError, extract_audio
from app.config import load_settings
from app.downloader import DownloadError, download_video
from app.metadata import MetadataError
from app.project import ProjectNotFoundError, create_project, load_project, resolve_project_dir, update_status

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


if __name__ == "__main__":
    app()
