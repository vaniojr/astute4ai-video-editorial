"""Renderização do vídeo final (intro + corte com overlays + CTA) via FFmpeg.

Composição por filtro `concat` (não o demuxer `-f concat`) — robusto a
pequenas diferenças de parâmetro de encoding entre a intro/CTA (geradas na
hora) e o corte (já codificado por `app/cutter.py`), porque opera sobre
frames decodificados, não sobre bitstream.

Cards de contexto/subtema e a atribuição de fonte são desenhados **sobre**
o próprio corte (não são segmentos concatenados) — `drawtext` encadeado no
stream de vídeo do corte, com `enable='between(t,inicio,fim)'` controlando
quando cada um aparece. Os timestamps dos cards já saem em segundos
relativos ao corte desde `app/editorial_planner.py`, usados direto aqui
sem conversão (a IA nunca decide esse valor — seção 34 do documento de
referência). Lower thirds não são renderizados ainda: o dado nunca é
preenchido (sem registro de participantes), não há nada a desenhar.

Intro/CTA/cards/atribuição de fonte em texto exigem
`brand.assets.primary_font` configurado — sem fonte, todos são
simplesmente pulados (aviso claro no resultado), nunca falham o render
inteiro: o corte sozinho já é um `final/*.mp4` válido (mesmo princípio do
modo `manual` da thumbnail — nunca travar o pipeline por um recurso
opcional em falta).

O CTA tem 3 formas possíveis (`Cta.text`/`.image`/`.video`, exatamente uma
preenchida — garantido na origem por `app/brands.py`): texto gerado na
hora (como acima), imagem estática ou vídeo pronto anexado como segmento
— estes dois últimos não precisam de fonte, já que não desenham texto.
"""

import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.analysis import AnalysisError, get_video_duration_seconds
from app.brands import Brand
from app.config import Settings
from app.editorial_models import ContextCard, EditorialPlan
from app.ffmpeg_utils import INSTALL_HINT as FFMPEG_INSTALL_HINT
from app.ffmpeg_utils import VideoProperties, is_binary_available, probe_video_properties, run, truncate_stderr

_WRAP_CHARS = 40
_CARD_WRAP_CHARS = 30


class EditorialRenderError(Exception):
    """Erro acionável na renderização do vídeo editorial final."""


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    intro_included: bool
    cta_included: bool
    cards_included: int = 0
    source_attribution_included: bool = False
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
    cta = editorial_plan.cta
    cta_kind: Optional[str] = (
        "text" if (cta.text or "").strip() else "image" if cta.image else "video" if cta.video else None
    )
    want_cta = cta.enabled and cta_kind is not None
    cards = [c for c in editorial_plan.context_cards if (c.text or "").strip()]
    want_source_attribution = bool((editorial_plan.source_attribution.text or "").strip())

    # CTA por imagem/vídeo não desenha texto nenhum — só intro/CTA em texto/cards/
    # atribuição dependem de `primary_font` configurada.
    want_text_overlays = want_intro or cta_kind == "text" or bool(cards) or want_source_attribution
    skipped_reason = None
    if want_text_overlays and not font_available:
        skipped_reason = (
            f"Marca '{brand.slug}' não tem uma fonte configurada "
            "(brand.assets.primary_font) — intro/CTA em texto/cards/atribuição de fonte foram pulados."
        )
        want_intro = False
        cards = []
        want_source_attribution = False
        if cta_kind == "text":
            want_cta = False
            cta_kind = None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not want_intro and not want_cta and not cards and not want_source_attribution:
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
            cta_kind=cta_kind,
            cards=cards,
            want_source_attribution=want_source_attribution,
        )
        result = run(cmd)
        if result.returncode != 0:
            raise EditorialRenderError(
                f"FFmpeg falhou ao renderizar '{output_path.name}':\n\n{truncate_stderr(result.stderr)}"
            )

    return RenderResult(
        output_path=output_path,
        intro_included=want_intro,
        cta_included=want_cta,
        cards_included=len(cards),
        source_attribution_included=want_source_attribution,
        skipped_text_reason=skipped_reason,
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
    cta_kind: Optional[str],
    cards: List[ContextCard],
    want_source_attribution: bool,
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
    cut_video_filter = _build_cut_overlay_chain(
        editorial_plan,
        cards=cards,
        want_source_attribution=want_source_attribution,
        font_path=font_path,
        text_color=text_color,
        bg_color=bg_color,
        fontsize=fontsize,
        settings=settings,
        work_dir=work_dir,
    )
    filter_lines.append(f"[{input_index}:v]{cut_video_filter}format=yuv420p[cut_v]")
    filter_lines.append(
        f"[{input_index}:a]aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[cut_a]"
    )
    segments.append(("cut_v", "cut_a"))
    input_index += 1

    if want_cta and cta_kind == "text":
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
    elif want_cta and cta_kind == "image":
        input_index = _append_image_card_inputs(
            argv,
            filter_lines,
            segments,
            label="cta",
            image_path=Path(editorial_plan.cta.image),
            duration=settings.editorial_cta_seconds,
            props=props,
            bg_color=bg_color,
            input_index=input_index,
        )
    elif want_cta and cta_kind == "video":
        input_index = _append_cta_video_inputs(
            argv,
            filter_lines,
            segments,
            label="cta",
            video_path=Path(editorial_plan.cta.video),
            props=props,
            bg_color=bg_color,
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


def _build_cut_overlay_chain(
    editorial_plan: EditorialPlan,
    *,
    cards: List[ContextCard],
    want_source_attribution: bool,
    font_path: Optional[Path],
    text_color: str,
    bg_color: str,
    fontsize: int,
    settings: Settings,
    work_dir: Path,
) -> str:
    """Cadeia de `drawtext,` (com vírgula final) a aplicar sobre o corte, na ordem.

    Cada card/atribuição de fonte é um estágio `drawtext` adicional com
    `enable='between(t,inicio,fim)'` — sobre o próprio stream do corte, não
    um segmento novo. Retorna string vazia se nada for aplicado.
    """
    stages: List[str] = []
    card_fontsize = max(18, int(fontsize * 0.7))

    for index, card in enumerate(cards, start=1):
        text_path = work_dir / f"card_{index:02d}.txt"
        text_path.write_text(_wrap_text(card.text, width=_CARD_WRAP_CHARS), encoding="utf-8")
        start = max(card.timestamp, 0.0)
        end = start + settings.editorial_card_seconds
        stages.append(
            f"drawtext=fontfile={_escape_filter_value(str(font_path))}:"
            f"textfile={_escape_filter_value(str(text_path))}:fontsize={card_fontsize}:"
            f"fontcolor={text_color}:x=(w-text_w)/2:y=h-text_h-40:"
            f"box=1:boxcolor={bg_color}@0.7:boxborderw=10:line_spacing=6:"
            f"enable='between(t,{start},{end})'"
        )

    if want_source_attribution:
        text_path = work_dir / "source_attribution.txt"
        text_path.write_text(
            _wrap_text(editorial_plan.source_attribution.text, width=_CARD_WRAP_CHARS), encoding="utf-8"
        )
        duration = settings.editorial_source_attribution_seconds
        attribution_fontsize = max(14, int(fontsize * 0.5))
        stages.append(
            f"drawtext=fontfile={_escape_filter_value(str(font_path))}:"
            f"textfile={_escape_filter_value(str(text_path))}:fontsize={attribution_fontsize}:"
            f"fontcolor={text_color}:x=w-text_w-20:y=h-text_h-20:"
            f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
            f"enable='between(t,0,{duration})'"
        )

    return "".join(f"{stage}," for stage in stages)


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


def _append_image_card_inputs(
    argv: List[str],
    filter_lines: List[str],
    segments: List[Tuple[str, str]],
    *,
    label: str,
    image_path: Path,
    duration: float,
    props: VideoProperties,
    bg_color: str,
    input_index: int,
) -> int:
    argv += ["-loop", "1", "-t", str(duration), "-i", str(image_path)]
    video_index = input_index
    input_index += 1

    argv += ["-f", "lavfi", "-i", f"anullsrc=r={props.sample_rate}:cl=stereo"]
    audio_index = input_index
    input_index += 1

    video_label = f"{label}_v"
    audio_label = f"{label}_a"

    filter_lines.append(
        f"[{video_index}:v]{_letterbox_filter(props, bg_color)},format=yuv420p[{video_label}]"
    )
    filter_lines.append(
        f"[{audio_index}:a]atrim=duration={duration},"
        f"aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[{audio_label}]"
    )
    segments.append((video_label, audio_label))
    return input_index


def _append_cta_video_inputs(
    argv: List[str],
    filter_lines: List[str],
    segments: List[Tuple[str, str]],
    *,
    label: str,
    video_path: Path,
    props: VideoProperties,
    bg_color: str,
    input_index: int,
) -> int:
    """Anexa um vídeo pronto (`brand.video.cta_video`) como segmento do CTA.

    Diferente da intro/CTA em texto ou imagem, a duração é a do próprio
    arquivo (não `settings.editorial_cta_seconds`) — o vídeo já foi
    produzido no tamanho desejado. Reaproveita a trilha de áudio original
    quando existe; gera silêncio na duração certa quando não existe (em
    vez de tentar adivinhar/forçar uma trilha que não está lá).
    """
    try:
        cta_props = probe_video_properties(video_path)
        duration = get_video_duration_seconds(video_path)
    except (RuntimeError, AnalysisError) as exc:
        raise EditorialRenderError(str(exc)) from exc

    argv += ["-i", str(video_path)]
    video_index = input_index
    input_index += 1

    video_label = f"{label}_v"
    audio_label = f"{label}_a"

    filter_lines.append(
        f"[{video_index}:v]{_letterbox_filter(props, bg_color)},format=yuv420p[{video_label}]"
    )

    if cta_props.has_audio:
        filter_lines.append(
            f"[{video_index}:a]aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[{audio_label}]"
        )
    else:
        argv += ["-f", "lavfi", "-i", f"anullsrc=r={props.sample_rate}:cl=stereo"]
        audio_index = input_index
        input_index += 1
        filter_lines.append(
            f"[{audio_index}:a]atrim=duration={duration},"
            f"aformat=sample_rates={props.sample_rate}:channel_layouts=stereo[{audio_label}]"
        )

    segments.append((video_label, audio_label))
    return input_index


def _letterbox_filter(props: VideoProperties, bg_color: str) -> str:
    """Escala preservando proporção e preenche a sobra com `bg_color` (sem cortar).

    Diferente do recorte central usado em `app/thumbnail_service.py` (onde
    cortar uma foto de rosto é aceitável): aqui a imagem/vídeo do CTA
    normalmente já tem logo/texto posicionados de propósito, então cortar
    arriscaria cortar um elemento importante da peça.
    """
    return (
        f"scale={props.width}:{props.height}:force_original_aspect_ratio=decrease,"
        f"pad={props.width}:{props.height}:(ow-iw)/2:(oh-ih)/2:color={bg_color},"
        f"setsar=1,fps={props.fps}"
    )


def _wrap_text(text: str, *, width: int = _WRAP_CHARS) -> str:
    """Quebra linhas longas por largura, preservando quebras de linha já existentes.

    `textwrap.wrap()` sozinho colapsa `\\n` já presentes no texto (ex.:
    `brand.video.cta_text` configurado com quebra de linha proposital) antes
    de re-quebrar por largura — por isso quebramos parágrafo por parágrafo.
    """
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            lines.extend(textwrap.wrap(paragraph, width=width))
        else:
            lines.append("")
    return "\n".join(lines) if lines else text


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
