"""CLI do video-editorial (PRD seção 24)."""

import typer

from app.metadata import MetadataError
from app.project import create_project

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


if __name__ == "__main__":
    app()
