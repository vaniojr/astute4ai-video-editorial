"""Renderização do vídeo final (intro + corte + CTA) via FFmpeg.

Composição por filtro `concat` (não o demuxer `-f concat`) — robusto a
pequenas diferenças de parâmetro de encoding entre a intro/CTA (geradas na
hora) e o corte (já codificado por `app/cutter.py`), porque opera sobre
frames decodificados, não sobre bitstream.

Intro/CTA em texto exigem `brand.assets.primary_font` configurado — sem
fonte, são simplesmente pulados (aviso claro no resultado), nunca falham
o render inteiro: o corte sozinho já é um `final/*.mp4` válido (mesmo
princípio do modo `manual` da thumbnail — nunca travar o pipeline por um
recurso opcional em falta).
"""

import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.brands import Brand
from app.config import Settings
from app.editorial_models import EditorialPlan
from app.ffmpeg_utils import INSTALL_HINT as FFMPEG_INSTALL_HINT
from app.ffmpeg_utils import VideoProperties, is_binary_available, probe_video_properties, run, truncate_stderr

_WRAP_CHARS = 40


class EditorialRenderError(Exception):
    """Erro acionável na renderização do vídeo editorial final."""


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    intro_included: bool
    cta_included: bool
    skipped_text_reason: Optional[str] = None


def render_editorial_video(
    editorial_plan: EditorialPlan,
    cut_path: Path,
    brand: Brand,
    output_path: Path,
    settings: Settings,
) -> RenderResult:
    if not is_binary_available("ffmpeg"):
        raise EditorialRenderError(f"FFmpeg não foi encontrado.\n\n{FFMPEG_INSTALL_HINT}")

    try:
        props = probe_video_properties(cut_path)
    except RuntimeError as exc:
        raise EditorialRenderError(str(exc)) from exc

    font_path = brand.assets.primary_font
    font_available = font_path is not None and font_path.is_file()

    want_intro = editorial_plan.intro.mode == "text_only" and bool((editorial_plan.intro.text or "").strip())
    want_cta = editorial_plan.cta.enabled and bool((editorial_plan.cta.text or "").strip())

    skipped_reason = None
    if (want_intro or want_cta) and not font_available:
        skipped_reason = (
            f"Marca '{brand.slug}' não tem uma fonte configurada "
            "(brand.assets.primary_font) — intro/CTA em texto foram pulados."
        )
        want_intro = False
        want_cta = False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not want_intro and not want_cta:
        shutil.copyfile(cut_path, output_path)
        return RenderResult(
            output_path=output_path, intro_included=False, cta_included=False, skipped_text_reason=skipped_reason
        )

    with tempfile.TemporaryDirectory(prefix="video-editorial-render-") as tmp:
        work_dir = Path(tmp)
        cmd = _build_render_command(
            editorial_plan,
            cut_path=cut_path,
            brand=brand,
            font_path=font_path,
            props=props,
            settings=settings,
            output_path=output_path,
            work_dir=work_dir,
            want_intro=want_intro,
            want_cta=want_cta,
        )
        result = run(cmd)
        if result.returncode != 0:
            raise EditorialRenderError(
                f"FFmpeg falhou ao renderizar '{output_path.name}':\n\n{truncate_stderr(result.stderr)}"
            )

    return RenderResult(
        output_path=output_path, intro_included=want_intro, cta_included=want_cta, skipped_text_reason=skipped_reason
    )


def _build_render_command(
    editorial_plan: EditorialPlan,
    *,
    cut_path: Path,
    brand: Brand,
    font_path: Optional[Path],
    props: VideoProperties,
    settings: Settings,
    output_path: Path,
    work_dir: Path,
    want_intro: bool,
    want_cta: bool,
) -> List[str]:
    argv: List[str] = ["ffmpeg", "-y"]
    filter_lines: List[str] = []
    segments: List[Tuple[str, str]] = []
    input_index = 0

    bg_color = _to_ffmpeg_color(brand.colors.background, default="0x000000")
    text_color = _to_ffmpeg_color(brand.colors.text, default="0xFFFFFF")
    fontsize = max(24, props.height // 18)

    if want_intro:
        text_path = work_dir / "intro_text.txt"
        text_path.write_text(_wrap_text(editorial_plan.intro.text or ""), encoding="utf-8")
        input_index = _append_text_card_inputs(
            argv,
            filter_lines,
            segments,
            label="intro",
            duration=settings.editorial_intro_seconds,
            props=props,
            bg_color=bg_color,
            text_color=text_color,
            fontsize=fontsize,
            font_path=font_path,
            text_path=text_path,
            input_index=input_index,
        )

    argv += ["-i", str(cut_path)]
    filter_lines.append(f"[{input_index}:v]format=yuv420p[cut_v]")
    filter_lines.append(
        f"[{input_index}:a]aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[cut_a]"
    )
    segments.append(("cut_v", "cut_a"))
    input_index += 1

    if want_cta:
        text_path = work_dir / "cta_text.txt"
        text_path.write_text(_wrap_text(editorial_plan.cta.text or ""), encoding="utf-8")
        input_index = _append_text_card_inputs(
            argv,
            filter_lines,
            segments,
            label="cta",
            duration=settings.editorial_cta_seconds,
            props=props,
            bg_color=bg_color,
            text_color=text_color,
            fontsize=fontsize,
            font_path=font_path,
            text_path=text_path,
            input_index=input_index,
        )

    concat_refs = "".join(f"[{v}][{a}]" for v, a in segments)
    filter_lines.append(f"{concat_refs}concat=n={len(segments)}:v=1:a=1[outv][outa]")

    argv += [
        "-filter_complex",
        ";".join(filter_lines),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
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
        str(output_path),
    ]
    return argv


def _append_text_card_inputs(
    argv: List[str],
    filter_lines: List[str],
    segments: List[Tuple[str, str]],
    *,
    label: str,
    duration: float,
    props: VideoProperties,
    bg_color: str,
    text_color: str,
    fontsize: int,
    font_path: Optional[Path],
    text_path: Path,
    input_index: int,
) -> int:
    argv += ["-f", "lavfi", "-i", f"color=c={bg_color}:s={props.width}x{props.height}:r={props.fps}:d={duration}"]
    video_index = input_index
    input_index += 1

    argv += ["-f", "lavfi", "-i", f"anullsrc=r={props.sample_rate}:cl=stereo"]
    audio_index = input_index
    input_index += 1

    video_label = f"{label}_v"
    audio_label = f"{label}_a"

    filter_lines.append(
        f"[{video_index}:v]drawtext=fontfile={_escape_filter_value(str(font_path))}:"
        f"textfile={_escape_filter_value(str(text_path))}:fontsize={fontsize}:"
        f"fontcolor={text_color}:x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=8,format=yuv420p[{video_label}]"
    )
    filter_lines.append(
        f"[{audio_index}:a]atrim=duration={duration},"
        f"aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[{audio_label}]"
    )
    segments.append((video_label, audio_label))
    return input_index


def _wrap_text(text: str) -> str:
    return "\n".join(textwrap.wrap(text, width=_WRAP_CHARS)) or text


def _to_ffmpeg_color(hex_color: Optional[str], *, default: str) -> str:
    if not hex_color:
        return default
    return "0x" + hex_color.lstrip("#")


def _escape_filter_value(value: str) -> str:
    """Escapa um valor para uso entre aspas simples num filtro FFmpeg.

    Dentro de aspas simples, o parser de filtro do FFmpeg trata tudo como
    literal — exceto a própria aspa simples, que não tem escape direto e
    precisa fechar/escapar/reabrir a citação (`'\\''`). Não usar a mesma
    lógica de escaping de shell aqui (backslash e `:` são literais dentro
    das aspas simples do FFmpeg, diferente de shell).
    """
    escaped = value.replace("'", "'\\''")
    return f"'{escaped}'"
