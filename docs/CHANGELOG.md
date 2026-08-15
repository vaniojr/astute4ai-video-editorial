# Changelog

Histórico do que foi entregue, em ordem cronológica (mais recente primeiro).
Formato inspirado em [Keep a Changelog](https://keepachangelog.com/) — o
"o quê" de cada mudança relevante, não um registro linha a linha de código.
Para o "porquê" de decisões específicas, veja a mensagem do commit
correspondente (`git show <hash>`) ou o `PRD_Video_Editorial*.md` da época.

## 2026-08-15 — Logs completos + feedback em tempo real (`ca3847a`)

- `logs/pipeline.log` passa a registrar todas as etapas do pipeline
  (`init`, `download`, `audio`, `transcribe`, `analyze`, `cut`), não só
  `analyze`/`cut`.
- Cada etapa grava `resultado="iniciado"` antes do trabalho pesado começar
  e `"ok"`/`"erro"` com `duracao_segundos` no fim (`log_operation()` em
  `app/logging_utils.py`) — se o processo travar/for morto no meio, o
  `iniciado` já fica registrado.
- Feedback em tempo real no terminal, sem flag nova: `transcribe` mostra
  cada trecho conforme é transcrito; `cut` avisa qual capítulo está
  cortando antes de cada FFmpeg; `download`/`audio`/`analyze` avisam
  quando o trabalho pesado começa.
- Limiar de aviso de transcrição longa em `analyze --dry-run` corrigido de
  100 mil para 400 mil caracteres (o valor anterior disparava para
  transcrições normais de vídeo longo).

## 2026-08-15 — Automação da análise editorial via LLM, Fase A (`d76678a`)

- Novo comando `video-editorial analyze PROJECT`: gera `03 Analise.csv`
  automaticamente via API da Claude, a partir de `01 Fonte.md` +
  `02 Transcricao.md`.
- Arquitetura plugável (`AnalysisProvider` em `app/analyzer.py`) — só
  `app/claude_provider.py` importa o SDK `anthropic`; `cut` continua
  completamente alheio a qual provider (ou processo manual) gerou o CSV.
- Structured output via tool use (nunca texto livre); resultado sempre
  revalidado pelo motor já existente (`app/analysis.py::evaluate_row`).
  Ordem de publicação e duração de cada capítulo são sempre calculadas
  pelo código, nunca aceitas do modelo.
- `--dry-run` (plano sem custo), confirmação antes de qualquer chamada
  real, idempotência (`--force` para regenerar), `--provider`/`--model`
  configuráveis.
- Prompts versionados em `prompts/analysis/` (`system.md` +
  `editorial.md`), com as regras de neutralidade e sinalização de
  conteúdo sensível do documento de referência.
- Credenciais via `.env`/`ANTHROPIC_API_KEY` (`python-dotenv`), nunca em
  `project.json`/CSV/logs.
- Fase B (chunking de transcrições longas, `--resume`, versionamento de
  runs) fica para depois, por decisão deliberada.
- **Descoberto na validação real** (não em mock): o modelo
  `claude-sonnet-5` rejeita o parâmetro `temperature` — removido da
  chamada.

## 2026-08-15 — Entrega 7: Refinamento (`a0eb4e6`)

- Novo comando `video-editorial status PROJECT` — mostra status atual e
  presença de cada artefato do pipeline.
- `resolve_project_dir()` passa a aceitar o `source_id` isolado do vídeo
  (ex.: `status 7xgE4ZHNWRU`), além de nome de diretório/caminho.
- `app/cutter.py`/`app/analysis.py` passam a checar FFmpeg/ffprobe antes
  de usar (`shutil.which`) — corrige um `FileNotFoundError` cru quando
  FFmpeg não está instalado.
- Teste de integração fim-a-fim (`init→download→audio→transcribe→cut`).
- `templates/03_Analise_exemplo.csv` e `docs/PIPELINE.md` (walkthrough
  único de ponta a ponta).

## 2026-08-15 — Entrega 6: Cortes (`4a0acf9`)

- `video-editorial cut PROJECT` (sem `--dry-run`) gera os cortes de
  verdade via FFmpeg — modo `precise` (H.264/AAC, re-encoding) e `fast`
  (`-c copy`, com aviso sobre precisão de keyframe).
- Nomes de arquivo `{ordem:03d}_cap{capitulo:02d}_{slug}.mp4`; nunca
  sobrescreve corte já existente.
- Filtros `--priority`/`--chapter`/`--order` (`app/analysis.py::filter_chapters`).
- Log estruturado por execução (`app/logging_utils.py`, uso inicial
  restrito a `cut`/depois `analyze`).

## 2026-08-14 — Entrega 5: CSV (`66ed6b8`)

- `video-editorial cut PROJECT --dry-run`: lê `03 Analise.csv`, valida
  timestamps contra a duração real do vídeo (`ffprobe`), sem gerar vídeo.
- Parser de timestamp (`app/timestamps.py`) resolve automaticamente o
  caso clássico de planilhas que corrompem `MM:SS` em `MM:SS:00` —
  confia na leitura H:MM:SS quando cabe na duração do vídeo, só tenta a
  leitura corrigida quando não cabe, e só marca `AMBÍGUO` quando nenhuma
  leitura cabe.
- Classificação de Ação Editorial, detecção de capítulos duplicados e
  sobreposição de intervalos.

## 2026-08-14 — Entrega 4: Transcrição (`e5f2054`)

- `video-editorial transcribe PROJECT`: transcreve `audio/audio.wav` via
  `faster-whisper`, preservando timestamps.
- Interface plugável `TranscriptionProvider` (`app/transcriber.py`) —
  `FasterWhisperProvider` é a implementação inicial.
- Gera `02 Transcricao.md` (legível) e `transcricao.json` (segmentos
  estruturados).

## 2026-08-14 — Entrega 3: Áudio (`745bcde`)

- `video-editorial audio PROJECT`: extrai `audio/audio.wav` (mono,
  16 kHz) do vídeo original via FFmpeg, com `ffprobe` validando a trilha
  de áudio antes.

## 2026-08-14 — Entrega 2: Download (`a0db534`)

- `video-editorial download PROJECT`: baixa o vídeo original via
  `yt-dlp` (melhor qualidade disponível), idempotente por padrão
  (`--force` para rebaixar).

## 2026-08-14 — Entrega 1: Fundação (`4492cba`)

- Estrutura inicial do projeto (`app/`, `cli/`, `templates/`, `prompts/`,
  `tests/`), gerenciada com `uv`.
- `video-editorial init URL`: consulta metadados via `yt-dlp` (sem
  baixar), cria `projetos/YYYY-MM-DD_slug_ID/` com `project.json` e
  `01 Fonte.md`. Prevenção de duplicidade por `source_id`.
