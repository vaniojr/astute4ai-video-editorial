"""Modelo de projeto e criação de estrutura (PRD seções 6, 7, 8, 9, 10, 22)."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from string import Template
from typing import Optional

from app.config import Settings, load_settings
from app.metadata import fetch_metadata
from app.slug import slugify

_PROJECT_SUBDIRS = ("original", "audio", "cortes", "thumbs", "publicados", "logs")

# PRD seção 23 — ordem dos estágios do pipeline, usada por advance_status()
# para nunca regredir um status já mais avançado.
_STATUS_ORDER = (
    "created",
    "downloaded",
    "audio_ready",
    "transcribed",
    "analyzed",
    "validated",
    "cut",
    "published",
)

# templates/ fica ao lado de app/ na raiz do repositório (execução a partir do
# código-fonte via `uv run`, sem empacotamento de dados de template).
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "fonte.md"


@dataclass(frozen=True)
class Project:
    schema_version: int
    platform: str
    source_id: str
    source_url: str
    title: str
    channel: Optional[str]
    published_at: Optional[date]
    duration_seconds: Optional[int]
    slug: str
    created_at: datetime
    status: str


@dataclass(frozen=True)
class ProjectCreationResult:
    path: Path
    already_existed: bool
    project: Optional[Project]


class ProjectNotFoundError(Exception):
    """Erro acionável quando o argumento PROJECT não corresponde a um projeto."""


def resolve_project_dir(project_arg: str, settings: Settings) -> Path:
    """Resolve PROJECT para um diretório de projeto existente.

    Aceita o nome do diretório dentro de `projetos/` ou um caminho explícito
    (relativo, absoluto ou `.`). Resolução por source_id/slug fica para uma
    entrega futura (PRD seção 25).
    """
    candidates = (Path(project_arg), settings.projetos_dir / project_arg)
    for candidate in candidates:
        if (candidate / "project.json").is_file():
            return candidate

    raise ProjectNotFoundError(
        f"Projeto não encontrado: {project_arg}\n\n"
        f"Verifique se o diretório existe em '{settings.projetos_dir}' "
        "ou informe o caminho completo do projeto."
    )


def load_project(project_dir: Path) -> Project:
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    return Project(
        schema_version=data["schema_version"],
        platform=data["platform"],
        source_id=data["source_id"],
        source_url=data["source_url"],
        title=data["title"],
        channel=data.get("channel"),
        published_at=date.fromisoformat(data["published_at"]) if data.get("published_at") else None,
        duration_seconds=data.get("duration_seconds"),
        slug=data["slug"],
        created_at=datetime.fromisoformat(data["created_at"]),
        status=data["status"],
    )


def update_status(project_dir: Path, status: str) -> None:
    path = project_dir / "project.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = status
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def advance_status(project_dir: Path, status: str) -> None:
    """Como update_status(), mas nunca regride um status já mais avançado."""
    path = project_dir / "project.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    current = data["status"]
    current_index = _STATUS_ORDER.index(current) if current in _STATUS_ORDER else -1
    new_index = _STATUS_ORDER.index(status) if status in _STATUS_ORDER else -1

    if new_index <= current_index:
        return

    data["status"] = status
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_existing_project(source_id: str, projetos_dir: Path) -> Optional[Path]:
    if not projetos_dir.exists():
        return None
    suffix = f"_{source_id}"
    for entry in sorted(projetos_dir.iterdir()):
        if entry.is_dir() and entry.name.endswith(suffix):
            return entry
    return None


def create_project(url: str, settings: Optional[Settings] = None) -> ProjectCreationResult:
    settings = settings or load_settings()
    metadata = fetch_metadata(url)

    existing = find_existing_project(metadata.source_id, settings.projetos_dir)
    if existing is not None:
        return ProjectCreationResult(path=existing, already_existed=True, project=None)

    slug = slugify(metadata.title)
    date_str = (metadata.published_at or date.today()).isoformat()
    project_dir = settings.projetos_dir / f"{date_str}_{slug}_{metadata.source_id}"

    for subdir in _PROJECT_SUBDIRS:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    project = Project(
        schema_version=1,
        platform=metadata.platform,
        source_id=metadata.source_id,
        source_url=metadata.source_url,
        title=metadata.title,
        channel=metadata.channel,
        published_at=metadata.published_at,
        duration_seconds=metadata.duration_seconds,
        slug=slug,
        created_at=datetime.now().astimezone(),
        status="created",
    )

    _write_project_json(project, project_dir)
    _write_fonte_md(project, project_dir)

    return ProjectCreationResult(path=project_dir, already_existed=False, project=project)


def _write_project_json(project: Project, project_dir: Path) -> None:
    data = {
        "schema_version": project.schema_version,
        "platform": project.platform,
        "source_id": project.source_id,
        "source_url": project.source_url,
        "title": project.title,
        "channel": project.channel,
        "published_at": project.published_at.isoformat() if project.published_at else None,
        "duration_seconds": project.duration_seconds,
        "slug": project.slug,
        "created_at": project.created_at.isoformat(timespec="seconds"),
        "status": project.status,
    }
    (project_dir / "project.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_fonte_md(project: Project, project_dir: Path) -> None:
    fonte_path = project_dir / "01 Fonte.md"
    if fonte_path.exists():
        return

    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    content = template.substitute(
        titulo=project.title,
        canal=project.channel or "",
        url=project.source_url,
        id=project.source_id,
        data=project.published_at.isoformat() if project.published_at else "",
        duracao=_format_duration(project.duration_seconds),
    )
    fonte_path.write_text(content, encoding="utf-8")


def _format_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
