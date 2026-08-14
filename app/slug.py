"""Geração de slugs a partir de títulos (PRD seções 6, 21, 31)."""

import re
import unicodedata

_MAX_LENGTH = 60
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = _MAX_LENGTH) -> str:
    """Normaliza um texto livre para um slug seguro para nomes de diretório/arquivo.

    Remove acentos, aspas e pontuação; converte espaços em hífens; colapsa
    hífens repetidos; e trunca em um limite de tamanho razoável sem cortar
    no meio de uma palavra quando possível.
    """
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    lowered = without_accents.lower()
    slug = _NON_ALNUM.sub("-", lowered).strip("-")

    if len(slug) > max_length:
        truncated = slug[:max_length]
        if "-" in truncated:
            truncated = truncated.rsplit("-", 1)[0]
        slug = truncated.strip("-")

    return slug or "sem-titulo"
