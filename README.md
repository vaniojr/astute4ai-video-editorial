# Video Editorial

Ferramenta local para apoiar a produção editorial de vídeos longos, podcasts
e lives. Veja `PRD_Video_Editorial.md` para a visão completa do produto.

Status atual: **Entrega 1 — Fundação**. Apenas a criação de projetos
(`init`) está implementada. Download, áudio, transcrição, análise e cortes
pertencem a entregas futuras.

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

## Testes

```bash
uv run pytest
```
