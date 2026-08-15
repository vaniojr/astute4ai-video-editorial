"""Geração determinística do briefing.md e das opções de headline da thumbnail
(Feature_thumbnail.md seções 10 e 15).

Sem IA nesta fase — texto principal e opções de headline reaproveitam
campos do CSV que já passaram por revisão humana antes do corte (`Titulo
Sugerido`, `Pergunta Principal`, `Tema Principal`); nada é inventado, só
selecionado/deduplicado. Nunca inventa participante — `participants_unknown`
fica sempre `true` aqui, já que o registro de participantes ficou
deliberadamente fora de escopo na Fundação 8.0 (Feature_thumbnail.md seção
16 permite esse fallback explicitamente).
"""

from typing import List

from app.analysis import AnalysisRow
from app.brands import Brand
from app.project import Project

_MAX_HEADLINE_OPTIONS = 3

_RESTRICOES_PADRAO = [
    "Não inventar participantes.",
    "Não criar falas que não existam no conteúdo.",
    "Não atribuir uma opinião da IA ao canal.",
    "Não apresentar alegações não verificadas como fatos.",
]


def build_briefing(row: AnalysisRow, project: Project, brand: Brand) -> str:
    restricoes = list(_RESTRICOES_PADRAO)
    if row.trecho_para_validar_primeiro or row.observacoes:
        restricoes.append(
            'Conteúdo sinalizado para validação — preferir "Fulano afirma..."/"Segundo o '
            'participante..." em vez de apresentar como fato consumado.'
        )

    fonte = project.title
    if project.channel:
        fonte = f"{fonte} ({project.channel})"

    lines = [
        "# Thumbnail Briefing",
        "",
        "## Capítulo",
        row.capitulo,
        "",
        "## FATOS DO CORTE",
        f"Tema: {row.tema_principal or '(não informado)'}",
        f"Resumo: {row.resumo or '(não informado)'}",
        f"Pergunta principal: {row.pergunta_principal or '(não informado)'}",
        f"Fonte: {fonte}",
        "",
        "## SUGESTÃO EDITORIAL",
        f"Palavra-chave principal: {row.palavra_chave_principal or '(não informado)'}",
        "Participantes: não identificados (participants_unknown)",
        "",
        "## ELEMENTOS VISUAIS",
        f"Marca: {brand.name}",
        (
            f"Cores: primary={brand.colors.primary or '-'}, "
            f"background={brand.colors.background or '-'}, "
            f"text={brand.colors.text or '-'}, accent={brand.colors.accent or '-'}"
        ),
        "",
        "## TEXTO DA THUMBNAIL",
        f"Texto principal sugerido: {row.titulo_sugerido or '(não informado)'}",
        "",
        "## RESTRIÇÕES",
    ]
    lines.extend(f"- {restricao}" for restricao in restricoes)
    return "\n".join(lines) + "\n"


def build_headline_options(row: AnalysisRow) -> List[str]:
    """Até 3 candidatas de headline, derivadas mecanicamente de campos do CSV.

    Nenhum texto novo é gerado — só seleção/deduplicação de campos que já
    passaram por revisão humana. A primeira opção (`options[0]`) é sempre a
    usada automaticamente enquanto não houver seleção manual/IA.
    """
    candidates = [row.titulo_sugerido, row.pergunta_principal, row.tema_principal]

    options: List[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and candidate not in options:
            options.append(candidate)
        if len(options) == _MAX_HEADLINE_OPTIONS:
            break
    return options
