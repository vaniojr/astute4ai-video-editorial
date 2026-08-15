# Video Editorial

Ferramenta local para apoiar a produção editorial de vídeos longos, podcasts
e lives. Veja `PRD_Video_Editorial.md` para a visão completa do produto.

Status atual: **Entrega 3 — Áudio**. Criação de projetos (`init`), download
do vídeo original (`download`) e extração de áudio (`audio`) estão
implementados. Transcrição, análise e cortes pertencem a entregas futuras.

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

```bash
uv run video-editorial audio "projetos/2026-08-12_slug_ID"
```

Extrai o áudio do vídeo original (mono, 16 kHz, WAV) para `audio/audio.wav`,
usando `ffmpeg`/`ffprobe`. Requer que o vídeo já tenha sido baixado
(`download`). Também é idempotente por padrão — use `--force` para
reextrair. O arquivo é derivado e descartável.

## Testes

```bash
uv run pytest
```
