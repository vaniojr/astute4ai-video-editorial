"""Log estruturado por projeto (PRD seção 26).

Registra timestamp, etapa, comando, resultado e erro em `logs/pipeline.log`
(uma linha JSON por evento). Nunca deve registrar tokens, credenciais,
cookies ou segredos.
"""

import json
import time
from contextlib import contextmanager
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


@contextmanager
def log_operation(project_dir: Path, *, etapa: str, comando: str):
    """Grava início + fim (com duração) de uma etapa em `logs/pipeline.log`.

    Grava `resultado="iniciado"` ao entrar — se o processo travar ou for
    encerrado no meio, essa linha já fica registrada. Ao sair, grava
    `resultado="ok"` ou `"erro"` com `duracao_segundos`, e relança qualquer
    exceção original (quem chama continua tratando `DownloadError`/etc.
    normalmente).

    Produz (`yield`) um dicionário mutável — quem usa o `with` pode inserir
    campos nele (ex.: `extra["input_tokens"] = ...`) para que apareçam na
    linha final de sucesso, junto com `duracao_segundos`.
    """
    log_event(project_dir, etapa=etapa, comando=comando, resultado="iniciado")
    start = time.monotonic()
    extra: dict = {}
    try:
        yield extra
    except Exception as exc:
        duracao = round(time.monotonic() - start, 1)
        log_event(
            project_dir,
            etapa=etapa,
            comando=comando,
            resultado="erro",
            erro=str(exc),
            extra={"duracao_segundos": duracao, **extra},
        )
        raise
    else:
        duracao = round(time.monotonic() - start, 1)
        log_event(
            project_dir,
            etapa=etapa,
            comando=comando,
            resultado="ok",
            extra={"duracao_segundos": duracao, **extra},
        )
