"""Geração dos cortes via FFmpeg (PRD seções 19–21).

Reaproveita a validação de `app/analysis.py` (só corta linhas com
`status == "ok"`); linhas ambíguas/manuais/com erro/descartadas são
simplesmente puladas aqui — a falha de uma linha nunca aborta as demais.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.analysis import ChapterReport, DryRunReport
from app.config import Settings
from app.slug import slugify

_MODES = ("precise", "fast")


class CutterError(Exception):
    """Erro acionável de configuração da geração de cortes (não por linha)."""


@dataclass(frozen=True)
class CutOutcome:
    chapter: ChapterReport
    status: str  # "cut" | "skipped_exists" | "skipped_ineligible" | "error"
    output_path: Optional[Path] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class CutRunResult:
    outcomes: List[CutOutcome]

    @property
    def cut_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "cut")


def generate_cuts(
    report: DryRunReport, project_dir: Path, settings: Settings, *, mode: str = "precise"
) -> CutRunResult:
    if mode not in _MODES:
        raise CutterError(f"Modo inválido: '{mode}'. Use 'precise' ou 'fast'.")

    if shutil.which("ffmpeg") is None:
        raise CutterError(
            "FFmpeg não foi encontrado.\n\n"
            "Instale no macOS:\n\n"
            "brew install ffmpeg"
        )

    cortes_dir = project_dir / "cortes"
    cortes_dir.mkdir(parents=True, exist_ok=True)

    outcomes = []
    for chapter in report.chapters:
        if chapter.status != "ok":
            outcomes.append(CutOutcome(chapter=chapter, status="skipped_ineligible"))
            continue

        try:
            filename = _build_filename(chapter.row, settings)
        except CutterError as exc:
            outcomes.append(CutOutcome(chapter=chapter, status="error", message=str(exc)))
            continue

        output_path = cortes_dir / filename
        if output_path.exists():
            outcomes.append(
                CutOutcome(chapter=chapter, status="skipped_exists", output_path=output_path)
            )
            continue

        try:
            _run_ffmpeg_cut(
                report.video_path,
                output_path,
                chapter.start_seconds,
                chapter.end_seconds,
                mode,
                settings,
            )
        except CutterError as exc:
            outcomes.append(CutOutcome(chapter=chapter, status="error", message=str(exc)))
            continue

        outcomes.append(CutOutcome(chapter=chapter, status="cut", output_path=output_path))

    return CutRunResult(outcomes=outcomes)


def _build_filename(row, settings: Settings) -> str:
    try:
        ordem = int(row.ordem_publicacao)
    except (TypeError, ValueError):
        raise CutterError(f"Ordem Publicacao inválida para geração do nome: '{row.ordem_publicacao}'")
    try:
        capitulo = int(row.capitulo)
    except (TypeError, ValueError):
        raise CutterError(f"Capitulo inválido para geração do nome: '{row.capitulo}'")

    base_title = row.titulo_sugerido or row.tema_principal
    slug = slugify(base_title)
    return f"{ordem:03d}_cap{capitulo:02d}_{slug}.{settings.output_format}"


def _run_ffmpeg_cut(
    video_path: Path,
    output_path: Path,
    start_seconds: float,
    end_seconds: float,
    mode: str,
    settings: Settings,
) -> None:
    duration = end_seconds - start_seconds

    if mode == "precise":
        encoding_args = [
            "-c:v",
            "libx264",
            "-crf",
            str(settings.ffmpeg_crf),
            "-preset",
            settings.ffmpeg_preset,
            "-c:a",
            "aac",
            "-b:a",
            f"{settings.audio_bitrate_kbps}k",
            "-movflags",
            "+faststart",
        ]
    else:
        encoding_args = ["-c", "copy"]

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_seconds),
        "-i",
        str(video_path),
        "-t",
        str(duration),
        *encoding_args,
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise CutterError(
            f"FFmpeg falhou ao gerar '{output_path.name}':\n\n{result.stderr.strip()[-2000:]}"
        )
