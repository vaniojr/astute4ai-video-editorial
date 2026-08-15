"""Convenção única de versionamento (`vNNN`), compartilhada entre features.

Política simples: sempre o número mais alto já existente + 1 (nunca
preenche lacunas). Usado por editorialização (`final/*_vNNN.mp4`) e
thumbnail (`thumbs/.../thumbnail_vNNN.png`) — nenhuma das duas reimplementa
sua própria contagem de versão.
"""

import re
from pathlib import Path

_VERSION_PATTERN = re.compile(r"_v(\d{3})")


def format_version(number: int) -> str:
    return f"v{number:03d}"


def next_version_number(directory: Path, glob_pattern: str) -> int:
    """Retorna o próximo número de versão para arquivos que casam com `glob_pattern`.

    Procura o padrão `_vNNN` no nome de cada arquivo encontrado; ignora
    arquivos sem esse padrão. Sem nenhuma versão existente, retorna 1.
    """
    if not directory.is_dir():
        return 1

    highest = 0
    for path in directory.glob(glob_pattern):
        match = _VERSION_PATTERN.search(path.stem)
        if match:
            highest = max(highest, int(match.group(1)))

    return highest + 1
