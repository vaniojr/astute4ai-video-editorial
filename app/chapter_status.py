"""Agregador somente-leitura do estado de cada capítulo (PRD `News features.md` seção 7).

Cruza `03 Analise.csv` com os artefatos já presentes no disco — por ora só
`cortes/*.mp4`; editorialização e thumbnail entram aqui nas Entregas
8.1/9.1, lendo seus próprios `metadata.json`. Não é uma nova fonte de
verdade mutável: cada etapa continua gravando seu próprio estado, este
módulo só lê e resume para `video-editorial status`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.analysis import classify_action, load_analysis
from app.config import Settings
from app.cutter import CutterError, build_cut_filename

_CSV_FILENAME = "03 Analise.csv"


@dataclass(frozen=True)
class ChapterStatus:
    capitulo: str
    ordem_publicacao: str
    cut: bool
    cut_path: Optional[Path]


def get_chapter_statuses(project_dir: Path, settings: Settings) -> List[ChapterStatus]:
    csv_path = project_dir / _CSV_FILENAME
    if not csv_path.is_file():
        return []

    cortes_dir = project_dir / "cortes"
    statuses = []
    for row in load_analysis(csv_path):
        if classify_action(row.acao_editorial) != "keep":
            continue
        try:
            filename = build_cut_filename(row, settings)
        except CutterError:
            continue

        cut_path = cortes_dir / filename
        exists = cut_path.is_file()
        statuses.append(
            ChapterStatus(
                capitulo=row.capitulo,
                ordem_publicacao=row.ordem_publicacao,
                cut=exists,
                cut_path=cut_path if exists else None,
            )
        )
    return statuses
