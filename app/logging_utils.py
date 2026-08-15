"""Log estruturado por projeto (PRD seção 26).

Registra timestamp, etapa, comando, resultado e erro em `logs/pipeline.log`
(uma linha JSON por evento). Nunca deve registrar tokens, credenciais,
cookies ou segredos.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_LOG_FILENAME = "pipeline.log"


def log_event(
    project_dir: Path,
    *,
    etapa: str,
    comando: str,
    resultado: str,
    erro: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Grava um evento em `logs/pipeline.log`.

    `extra` mescla campos adicionais no JSON (ex.: provider/model/usage do
    `analyze`) — nunca deve conter tokens, credenciais, cookies ou segredos.
    """
    entry = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "etapa": etapa,
        "comando": comando,
        "resultado": resultado,
        "erro": erro,
    }
    if extra:
        entry.update(extra)
    log_path = project_dir / "logs" / _LOG_FILENAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
