"""Orquestração da análise editorial automatizada via LLM.

`AnalysisProvider` é a interface plugável — este módulo nunca importa o SDK
de nenhum provider concreto diretamente (ex.: `anthropic`); só
`app/claude_provider.py` faz isso. `app/cutter.py`/`cut` continuam
completamente alheios a este módulo: o contrato entre as duas etapas
continua sendo apenas `03 Analise.csv` (gerado aqui ou editado à mão, tanto
faz para quem lê depois).

A validação de cada capítulo reaproveita integralmente `app/analysis.py`
(`evaluate_row`, `build_dry_run_report`) — nenhuma segunda implementação de
parser/validador de timestamp ou ação editorial.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.analysis import (
    AnalysisError,
    AnalysisRow,
    DryRunReport,
    build_dry_run_report,
    get_video_duration_seconds,
    write_analysis_csv,
)
from app.config import Settings
from app.logging_utils import log_operation
from app.project import advance_status, load_project
from app.timestamps import (
    TimestampAmbiguousError,
    TimestampFormatError,
    TimestampOutOfRangeError,
    format_hms,
    parse_timestamp,
)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "analysis"
_CSV_FILENAME = "03 Analise.csv"
_FONTE_FILENAME = "01 Fonte.md"
_TRANSCRICAO_FILENAME = "02 Transcricao.md"

# Acima disso, o dry-run avisa que a transcrição pode ultrapassar o
# praticável numa única chamada — chunking real é Fase B, ainda não
# implementado. ~400 mil caracteres ainda ficam com folga sob o limite de
# contexto real dos modelos Claude atuais (~100 mil tokens em português);
# o valor anterior (100 mil caracteres, ~25-35 mil tokens) disparava o
# aviso para transcrições normais de vídeo longo.
_LONG_TRANSCRIPT_CHAR_THRESHOLD = 400_000


class AnalysisServiceError(Exception):
    """Erro acionável na orquestração da análise editorial (não específico de provider)."""


@dataclass(frozen=True)
class UsageInfo:
    input_tokens: int
    output_tokens: int
    api_calls: int = 1


@dataclass(frozen=True)
class ChapterCandidate:
    """Capítulo candidato, como retornado pelo provider — ainda não validado.

    Sem `ordem_publicacao` (atribuída aqui após ordenar por timestamp — nunca
    se confia na ordem de retorno da API) e sem `duracao` (sempre calculada
    pelo código a partir dos timestamps, nunca aceita do modelo).
    """

    prioridade: str
    capitulo: int
    bloco_editorial: str
    acao_editorial: str
    timestamp_inicial: str
    timestamp_final: str
    tema_principal: str
    titulo_sugerido: str
    palavra_chave_principal: str
    trecho_para_validar_primeiro: str
    resumo: str
    pergunta_principal: str
    independente: str
    precisa_contexto_anterior: str
    grau_de_confianca: str
    observacoes: str


@dataclass(frozen=True)
class AnalysisRequest:
    source_content: str
    transcript_content: str
    system_instructions: str
    editorial_instructions: str
    metadata: Dict[str, str]


@dataclass(frozen=True)
class AnalysisResult:
    chapters: List[ChapterCandidate]
    provider: str
    model: str
    usage: Optional[UsageInfo] = None


class AnalysisProvider(ABC):
    @abstractmethod
    def analyze(self, request: AnalysisRequest) -> AnalysisResult: ...


def get_analysis_provider(name: str, *, model: str, temperature: float) -> AnalysisProvider:
    if name == "claude":
        from app.claude_provider import ClaudeAnalysisProvider

        return ClaudeAnalysisProvider(model=model, temperature=temperature)
    raise AnalysisServiceError(
        f"Provider de análise '{name}' ainda não implementado. Disponíveis: claude."
    )


@dataclass(frozen=True)
class AnalysisPlan:
    project_dir: Path
    provider: str
    model: str
    source_path: Path
    transcript_path: Path
    transcript_char_count: int
    csv_path: Path
    already_exists: bool
    long_transcript_warning: Optional[str]


def plan_analysis(
    project_dir: Path,
    settings: Settings,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> AnalysisPlan:
    """Monta o plano da análise sem chamar nenhuma API (usado por --dry-run)."""
    source_path = project_dir / _FONTE_FILENAME
    transcript_path = project_dir / _TRANSCRICAO_FILENAME
    csv_path = project_dir / _CSV_FILENAME

    if not source_path.exists():
        raise AnalysisServiceError(
            "01 Fonte.md não encontrado.\n\n"
            f"Esperado em: {source_path}\n\n"
            "Execute 'video-editorial init URL' primeiro."
        )
    if not transcript_path.exists():
        raise AnalysisServiceError(
            "02 Transcricao.md não encontrado.\n\n"
            f"Esperado em: {transcript_path}\n\n"
            "Execute 'video-editorial transcribe PROJECT' primeiro."
        )

    transcript_char_count = len(transcript_path.read_text(encoding="utf-8"))

    warning = None
    if transcript_char_count > _LONG_TRANSCRIPT_CHAR_THRESHOLD:
        warning = (
            f"Transcrição tem {transcript_char_count:,} caracteres, acima do limiar de "
            f"{_LONG_TRANSCRIPT_CHAR_THRESHOLD:,} usado nesta versão. Divisão em blocos "
            "(chunking) para transcrições longas ainda não está implementada — a chamada "
            "pode falhar ou custar mais do que o esperado."
        )

    return AnalysisPlan(
        project_dir=project_dir,
        provider=provider or settings.analysis_provider,
        model=model or settings.analysis_model,
        source_path=source_path,
        transcript_path=transcript_path,
        transcript_char_count=transcript_char_count,
        csv_path=csv_path,
        already_exists=csv_path.exists(),
        long_transcript_warning=warning,
    )


@dataclass(frozen=True)
class AnalyzeResult:
    plan: AnalysisPlan
    skipped: bool
    dry_run_report: Optional[DryRunReport] = None
    usage: Optional[UsageInfo] = None


def analyze_project(
    project_dir: Path,
    settings: Settings,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    force: bool = False,
) -> AnalyzeResult:
    plan = plan_analysis(project_dir, settings, provider=provider, model=model)

    if plan.already_exists and not force:
        return AnalyzeResult(plan=plan, skipped=True)

    comando = f"analyze {project_dir.name} --provider={plan.provider} --model={plan.model} --force={force}"

    with log_operation(project_dir, etapa="analyze", comando=comando) as log_extra:
        project = load_project(project_dir)
        request = AnalysisRequest(
            source_content=plan.source_path.read_text(encoding="utf-8"),
            transcript_content=plan.transcript_path.read_text(encoding="utf-8"),
            system_instructions=_load_prompt("system.md"),
            editorial_instructions=_load_prompt("editorial.md"),
            metadata={
                "titulo": project.title,
                "canal": project.channel or "",
                "duracao_segundos": str(project.duration_seconds or ""),
            },
        )

        analysis_provider = get_analysis_provider(
            plan.provider, model=plan.model, temperature=settings.analysis_temperature
        )
        result = analysis_provider.analyze(request)

        if not result.chapters:
            raise AnalysisServiceError(
                f"O provider '{plan.provider}' não retornou nenhum capítulo para esta transcrição."
            )

        video_path = project_dir / "original" / "video-original.mp4"
        video_duration = get_video_duration_seconds(video_path) if video_path.exists() else None

        ordered = _consolidate(result.chapters)
        rows = [
            _to_analysis_row(candidate, ordem_publicacao=i, capitulo=i, video_duration=video_duration)
            for i, candidate in enumerate(ordered, start=1)
        ]

        write_analysis_csv(plan.csv_path, rows)
        advance_status(project_dir, "analyzed")

        try:
            dry_run_report = build_dry_run_report(project_dir)
        except AnalysisError:
            # CSV já foi escrito com sucesso; só não há vídeo para validar contra
            # (situação incomum — 'transcribe' já exige 'download' antes).
            dry_run_report = None

        log_extra["provider"] = plan.provider
        log_extra["model"] = plan.model
        log_extra["input_tokens"] = result.usage.input_tokens if result.usage else None
        log_extra["output_tokens"] = result.usage.output_tokens if result.usage else None

    return AnalyzeResult(plan=plan, skipped=False, dry_run_report=dry_run_report, usage=result.usage)


def _consolidate(chapters: List[ChapterCandidate]) -> List[ChapterCandidate]:
    """Ordena por timestamp inicial — nunca confia na ordem de retorno da API.

    Fase B (chunking) reaproveita este mesmo passo para also remover
    duplicatas entre blocos adjacentes; nesta fase (uma chamada só) a
    ordenação já é suficiente.
    """

    def sort_key(candidate: ChapterCandidate) -> float:
        try:
            return parse_timestamp(candidate.timestamp_inicial, None).seconds
        except (TimestampFormatError, TimestampOutOfRangeError, TimestampAmbiguousError):
            return float("inf")

    return sorted(chapters, key=sort_key)


def _to_analysis_row(
    candidate: ChapterCandidate,
    *,
    ordem_publicacao: int,
    capitulo: int,
    video_duration: Optional[float],
) -> AnalysisRow:
    duracao = ""
    try:
        start = parse_timestamp(candidate.timestamp_inicial, video_duration)
        end = parse_timestamp(candidate.timestamp_final, video_duration)
        if end.seconds > start.seconds:
            duracao = format_hms(end.seconds - start.seconds)
    except (TimestampFormatError, TimestampOutOfRangeError, TimestampAmbiguousError):
        pass  # evaluate_row() relata o problema em detalhe no relatório

    return AnalysisRow(
        ordem_publicacao=str(ordem_publicacao),
        prioridade=candidate.prioridade,
        capitulo=str(capitulo),
        bloco_editorial=candidate.bloco_editorial,
        acao_editorial=candidate.acao_editorial,
        timestamp_inicial=candidate.timestamp_inicial,
        timestamp_final=candidate.timestamp_final,
        duracao=duracao,
        tema_principal=candidate.tema_principal,
        titulo_sugerido=candidate.titulo_sugerido,
        palavra_chave_principal=candidate.palavra_chave_principal,
        trecho_para_validar_primeiro=candidate.trecho_para_validar_primeiro,
        resumo=candidate.resumo,
        pergunta_principal=candidate.pergunta_principal,
        independente=candidate.independente,
        precisa_contexto_anterior=candidate.precisa_contexto_anterior,
        grau_de_confianca=candidate.grau_de_confianca,
        observacoes=candidate.observacoes,
    )


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
