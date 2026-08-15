"""Provider de análise editorial via API da Claude (Anthropic).

Único módulo do projeto que importa o SDK `anthropic` — `app/analyzer.py`
(orquestração) e `app/cutter.py` (`cut`) nunca dependem dele. Structured
output via tool use (function calling): a Claude é forçada a chamar uma
única ferramenta cujo schema já restringe tipos/enums dos campos, e o
resultado ainda passa pela validação semântica de `app/analysis.py` — a
saída do modelo é sempre tratada como dado, nunca como verdade aceita
silenciosamente.
"""

import os
from typing import Any, Dict, List

import anthropic

from app.analyzer import (
    AnalysisProvider,
    AnalysisRequest,
    AnalysisResult,
    AnalysisServiceError,
    ChapterCandidate,
    UsageInfo,
)

_TOOL_NAME = "submeter_analise_editorial"
_MAX_TOKENS = 8192

_PRIORIDADE_VALUES = ["A", "B", "C"]
_ACAO_EDITORIAL_VALUES = [
    "Manter",
    "Revisar",
    "Descartar",
    "Nao publicar",
    "Arquivar",
    "Unir",
    "Separar",
    "Transformar em teaser",
]
_GRAU_CONFIANCA_VALUES = ["Alto", "Medio", "Baixo"]
_SIM_NAO_VALUES = ["Sim", "Nao"]

_CHAPTER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "capitulo": {
            "type": "integer",
            "description": "Número sequencial do capítulo dentro desta transcrição, começando em 1.",
        },
        "prioridade": {"type": "string", "enum": _PRIORIDADE_VALUES},
        "bloco_editorial": {"type": "string"},
        "acao_editorial": {"type": "string", "enum": _ACAO_EDITORIAL_VALUES},
        "timestamp_inicial": {
            "type": "string",
            "description": "Formato HH:MM:SS, copiado da transcrição fornecida.",
        },
        "timestamp_final": {
            "type": "string",
            "description": "Formato HH:MM:SS, copiado da transcrição fornecida.",
        },
        "tema_principal": {"type": "string"},
        "titulo_sugerido": {"type": "string"},
        "palavra_chave_principal": {"type": "string"},
        "trecho_para_validar_primeiro": {"type": "string"},
        "resumo": {"type": "string"},
        "pergunta_principal": {"type": "string"},
        "independente": {"type": "string", "enum": _SIM_NAO_VALUES},
        "precisa_contexto_anterior": {"type": "string", "enum": _SIM_NAO_VALUES},
        "grau_de_confianca": {"type": "string", "enum": _GRAU_CONFIANCA_VALUES},
        "observacoes": {"type": "string"},
    },
    "required": [
        "capitulo",
        "prioridade",
        "acao_editorial",
        "timestamp_inicial",
        "timestamp_final",
        "tema_principal",
        "titulo_sugerido",
        "resumo",
        "independente",
        "precisa_contexto_anterior",
        "grau_de_confianca",
    ],
}

_TOOL_DEFINITION: Dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Submete a lista de capítulos editoriais identificados na transcrição.",
    "input_schema": {
        "type": "object",
        "properties": {
            "capitulos": {"type": "array", "items": _CHAPTER_SCHEMA},
        },
        "required": ["capitulos"],
    },
}


class ClaudeAnalysisProvider(AnalysisProvider):
    def __init__(self, model: str, temperature: float, *, max_retries: int = 3):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AnalysisServiceError(
                "ANTHROPIC_API_KEY não definida.\n\n"
                "Defina a variável de ambiente ou crie um arquivo .env "
                "(veja .env.example) antes de rodar 'analyze'."
            )
        self._model = model
        self._temperature = temperature
        # max_retries: o SDK já reage sozinho a erros transitórios (rate
        # limit, timeout, 5xx) com backoff — não reimplementamos retry aqui.
        self._client = anthropic.Anthropic(max_retries=max_retries)

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        # `temperature` não é enviado: a API rejeita esse parâmetro para
        # modelos mais recentes como claude-sonnet-5 ("`temperature` is
        # deprecated for this model", confirmado numa chamada real). O
        # campo `analysis_temperature` continua reservado em `Settings`
        # para quando algum provider/modelo voltar a aceitá-lo.
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=request.system_instructions,
                tools=[_TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": _build_user_message(request)}],
            )
        except anthropic.AuthenticationError as exc:
            raise AnalysisServiceError(
                "Credencial inválida para a API da Claude (ANTHROPIC_API_KEY)."
            ) from exc
        except anthropic.AnthropicError as exc:
            raise AnalysisServiceError(f"Falha ao chamar a API da Claude: {exc}") from exc

        tool_use = next(
            (block for block in message.content if getattr(block, "type", None) == "tool_use"), None
        )
        if tool_use is None:
            raise AnalysisServiceError(
                "A resposta da Claude não incluiu o resultado estruturado esperado."
            )

        chapters = _parse_chapters(tool_use.input)

        usage = None
        if message.usage is not None:
            usage = UsageInfo(
                input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens
            )

        return AnalysisResult(chapters=chapters, provider="claude", model=self._model, usage=usage)


def _build_user_message(request: AnalysisRequest) -> str:
    metadata_lines = "\n".join(f"{key}: {value}" for key, value in request.metadata.items())
    return (
        f"{request.editorial_instructions}\n\n"
        "---\n\n"
        f"## Metadados do projeto\n\n{metadata_lines}\n\n"
        "---\n\n"
        f"## Fonte (01 Fonte.md)\n\n{request.source_content}\n\n"
        "---\n\n"
        f"## Transcrição (02 Transcricao.md)\n\n{request.transcript_content}"
    )


def _parse_chapters(raw_input: Any) -> List[ChapterCandidate]:
    if not isinstance(raw_input, dict) or "capitulos" not in raw_input:
        raise AnalysisServiceError(
            "Resposta estruturada da Claude não contém o campo 'capitulos' esperado."
        )

    raw_chapters = raw_input["capitulos"]
    if not isinstance(raw_chapters, list):
        raise AnalysisServiceError("'capitulos' na resposta da Claude deveria ser uma lista.")

    chapters = []
    for index, raw in enumerate(raw_chapters):
        if not isinstance(raw, dict):
            raise AnalysisServiceError(f"Capítulo {index} da resposta não é um objeto válido.")
        try:
            chapters.append(
                ChapterCandidate(
                    prioridade=str(raw["prioridade"]),
                    capitulo=int(raw["capitulo"]),
                    bloco_editorial=str(raw.get("bloco_editorial", "")),
                    acao_editorial=str(raw["acao_editorial"]),
                    timestamp_inicial=str(raw["timestamp_inicial"]),
                    timestamp_final=str(raw["timestamp_final"]),
                    tema_principal=str(raw["tema_principal"]),
                    titulo_sugerido=str(raw["titulo_sugerido"]),
                    palavra_chave_principal=str(raw.get("palavra_chave_principal", "")),
                    trecho_para_validar_primeiro=str(raw.get("trecho_para_validar_primeiro", "")),
                    resumo=str(raw["resumo"]),
                    pergunta_principal=str(raw.get("pergunta_principal", "")),
                    independente=str(raw["independente"]),
                    precisa_contexto_anterior=str(raw["precisa_contexto_anterior"]),
                    grau_de_confianca=str(raw["grau_de_confianca"]),
                    observacoes=str(raw.get("observacoes", "")),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise AnalysisServiceError(
                f"Capítulo {index} da resposta da Claude está incompleto ou mal formatado: {exc}"
            ) from exc

    return chapters
