# Video Editorial

Ferramenta local para apoiar a produção editorial de vídeos longos, podcasts
e lives. Veja `PRD_Video_Editorial.md` para a visão completa do produto.

Status atual: **Entrega 2 — Download**. Criação de projetos (`init`) e
download do vídeo original (`download`) estão implementados. Áudio,
transcrição, análise e cortes pertencem a entregas futuras.

## Setup

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Uso

```bash
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID"
```

Isso consulta os metadados do vídeo (via `yt-dlp`, sem baixar o arquivo),
cria um diretório único em `projetos/` no formato `YYYY-MM-DD_slug_ID` e
gera `project.json` e `01 Fonte.md`.

Executar novamente com a mesma URL não cria um projeto duplicado — a
ferramenta identifica o projeto existente pelo ID do vídeo e apenas informa
o caminho.

```bash
uv run video-editorial download "projetos/2026-08-12_slug_ID"
```

Baixa o vídeo original (melhor qualidade disponível, vídeo+áudio combinados
via FFmpeg) para `original/video-original.mp4`. Requer FFmpeg instalado
(`brew install ffmpeg` no macOS). `PROJECT` pode ser o nome do diretório
dentro de `projetos/` ou um caminho explícito (relativo, absoluto ou `.`
quando executado de dentro do projeto).

Se o arquivo já existir, nenhum download é refeito — use `--force` para
baixar novamente e substituir o arquivo existente.

## Testes

```bash
uv run pytest
```
