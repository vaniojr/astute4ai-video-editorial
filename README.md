# Video Editorial

Ferramenta local para apoiar a produção editorial de vídeos longos, podcasts
e lives. Veja `PRD_Video_Editorial.md` para a visão completa do produto.

Status atual: **Entrega 5 — CSV**. Criação de projetos (`init`), download
do vídeo original (`download`), extração de áudio (`audio`), transcrição
(`transcribe`) e validação/dry-run da análise editorial (`cut --dry-run`)
estão implementados. A geração real dos cortes pertence à próxima entrega.

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

```bash
uv run video-editorial transcribe "projetos/2026-08-12_slug_ID"
```

Transcreve `audio/audio.wav` preservando timestamps, usando
[faster-whisper](https://github.com/SYSTRAN/faster-whisper). Gera
`02 Transcricao.md` (legível, com blocos `[HH:MM:SS → HH:MM:SS]`) e
`transcricao.json` (segmentos estruturados, para uso na análise editorial).
Requer que o áudio já tenha sido extraído (`audio`). Idempotente por
padrão — use `--force` para retranscrever.

O modelo (`VIDEO_EDITORIAL_WHISPER_MODEL`, padrão `medium`) é baixado
automaticamente do Hugging Face Hub no primeiro uso — a primeira execução
requer conexão com a internet e pode demorar. O idioma padrão
(`VIDEO_EDITORIAL_WHISPER_LANGUAGE`) é `pt`.

```bash
uv run video-editorial cut "projetos/2026-08-12_slug_ID" --dry-run
```

A análise editorial (`03 Analise.csv`) ainda é produzida externamente
(Claude no VS Code, a partir de `01 Fonte.md` e `02 Transcricao.md`) — não
há geração automática nesta versão. O `cut --dry-run` lê esse CSV, valida
cada linha e mostra os cortes elegíveis, **sem gerar nenhum vídeo**.

Colunas reconhecidas (nomes exatos, qualquer ordem):
`Ordem Publicacao`, `Prioridade`, `Capitulo`, `Bloco Editorial`,
`Acao Editorial`, `Timestamp Inicial`, `Timestamp Final`, `Duracao`,
`Tema Principal`, `Titulo Sugerido`, `Palavra-chave Principal`,
`Trecho para Validar Primeiro`, `Resumo`, `Pergunta Principal`,
`Independente`, `Precisa Contexto Anterior`, `Grau de Confianca`,
`Observacoes`. As cinco primeiras são obrigatórias.

`Acao Editorial` reconhecida:
- `Manter` → elegível para corte.
- `Descartar` / `Não publicar` / `Arquivar` → ignorado.
- `Unir` / `Separar` / `Transformar em teaser` / `Revisar` → não executado
  automaticamente; aparece como `[AVISO]` no relatório.

Timestamps aceitam `MM:SS`, `H:MM:SS`, e as variantes que planilhas geram
ao exportar (`MM:SS:00`, `H:MM:SS:00`). Quando um valor como `29:07:00` é
ambíguo entre "29 horas" e "29 minutos", o sistema usa a duração real do
vídeo para escolher a única leitura plausível e reporta a correção
explicitamente no relatório; só marca `[AMBÍGUO]` (sem cortar aquele
registro) quando as duas leituras cabem na duração do vídeo, nenhuma cabe,
ou a duração não pôde ser obtida.

Sem `--dry-run`, `cut` ainda não gera cortes reais (reservado para a
próxima entrega).

## Testes

```bash
uv run pytest
```
