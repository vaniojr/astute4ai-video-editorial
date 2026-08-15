# Changelog

Histórico do que foi entregue, em ordem cronológica (mais recente primeiro).
Formato inspirado em [Keep a Changelog](https://keepachangelog.com/) — o
"o quê" de cada mudança relevante, não um registro linha a linha de código.
Para o "porquê" de decisões específicas, veja a mensagem do commit
correspondente (`git show <hash>`) ou o `docs/PRD_Video_Editorial*.md` da
época. Para um resumo por versão (menos técnico), veja
[RELEASE_NOTES.md](RELEASE_NOTES.md).

## 2026-08-15 — Entrega 8.1: Editorial — Planner (sem renderização)

- Novo comando `video-editorial editorialize PROJECT --chapter N`: gera
  um plano editorial (`editorial_plan_vNNN.json`) via Claude — intro
  curta, cards de contexto/subtema, frases de destaque. **Não renderiza
  vídeo nenhum** (fica para uma entrega futura); o plano é só para
  revisão humana.
- Regra central (nunca violada): a IA nunca decide um timestamp em
  segundos, absoluto ou relativo. Cards vêm com uma posição normalizada
  (`position_fraction`, 0.0–1.0 da duração do corte) convertida para
  segundo por `app/editorial_planner.py`; frases de destaque só entram no
  plano se o texto realmente aparecer na transcrição real do corte
  (`app/editorial_planner.py::find_highlight_timing`) — citação que não
  bate com a transcrição é descartada, nunca inventada.
- `app/timestamps.py` ganha `to_relative_seconds()` — conversão
  determinística de timestamp absoluto (vídeo original) para relativo ao
  início do corte.
- Fonte (`source_attribution`) e CTA são sempre determinísticos — vêm dos
  metadados do projeto e do Brand Profile (`brand.video.cta_text`), nunca
  decididos pela IA (`lower_thirds` fica vazio nesta fase — sem registro
  de participantes ainda, mesma decisão já tomada para a thumbnail).
- `app/editorial_provider.py`/`app/editorial_claude_provider.py`: mesmo
  padrão ABC + factory + structured output via tool use já usado por
  `AnalysisProvider`/`ThumbnailProvider` — único arquivo que importa
  `anthropic` desta feature.
- `plan_editorial()` (usado por `--dry-run`) nunca chama o provider nem
  exige `ANTHROPIC_API_KEY` — mesmo padrão de `analyzer.py::plan_analysis()`.
- Só o trecho de transcrição correspondente ao corte é enviado à API
  (extraído de `transcricao.json`), nunca a transcrição inteira do vídeo.
- Versionamento (`editorial_plan_v001.json`, `v002.json`...) reaproveita
  `app/versioning.py`; idempotente por padrão, `--force` cria versão
  nova sem sobrescrever.
- `app/chapter_status.py` ganha o campo `editorial_planned`; `status`
  mostra os dois marcadores por capítulo (`cut`/`editorial (planejado)`).
- Prompts novos em `prompts/editorial/` (`system.md`/`editorial.md`),
  mesmo tom/regras de neutralidade do `prompts/analysis/`.
- Validado com uma chamada real (paga) à API da Claude, de ponta a ponta
  (`init → download → audio → transcribe → cut → editorialize`), sem
  mocks.

## 2026-08-15 — Thumbnail: abstração de provider, versionamento e aprovação

- `app/thumbnail_provider.py` (novo): `ThumbnailProvider` (ABC) +
  `get_thumbnail_provider()` (factory), mesmo padrão de
  `AnalysisProvider`/`get_analysis_provider()`. Contrato
  `ThumbnailRequest(reference_images, briefing, aspect_ratio="16:9",
  brand)` já pronto para múltiplas imagens de referência. `manual`
  continua sendo a única implementação — nunca gera imagem, nunca importa
  nenhum SDK de geração de imagem (nem OpenAI, nem Google, nem nenhum
  outro) enquanto nenhum provider real for escolhido.
- Provider só devolve bytes de imagem — quem decide nome de arquivo e
  aplica versionamento (`app/versioning.py`, `thumbnail_v001.png`,
  `v002.png`...) é `app/thumbnail_service.py`, mesma separação que
  `app/cutter.py` já usa para os cortes.
- Novo comando `video-editorial thumbnail-select PROJECT --chapter N
  --version N`: copia a versão escolhida para `selected.png` e marca
  `metadata.json` (`"selected"`, `"status": "selected"`) — aprovação
  sempre explícita, nunca automática.
- `metadata.json` ganha `headline_options` (até 3 candidatas derivadas
  mecanicamente de `Titulo Sugerido`/`Pergunta Principal`/`Tema
  Principal`, deduplicadas — nenhum texto novo é inventado, só
  selecionado entre campos já revisados por humano), `images` e
  `selected`.
- `thumbnail --dry-run` agora também mostra quantas versões de imagem já
  existem para o capítulo.
- `generate_thumbnail_briefing()`/`ThumbnailBriefingResult` renomeados
  para `generate_thumbnail()`/`ThumbnailGenerationResult` — o nome
  antigo não refletia mais o escopo (agora cobre frames + briefing +
  tentativa de geração de imagem).
- Validado manualmente com FFmpeg real de ponta a ponta, incluindo
  `thumbnail-select` contra arquivos de imagem fabricados à mão
  (simulando o que um provider real produziria).

## 2026-08-15 — Entrega 9.1: Thumbnail — frames + briefing (modo manual)

- Novo comando `video-editorial thumbnail PROJECT --chapter N [--dry-run]
  [--force]`: extrai 9 frames reais do corte já gerado (`cortes/`, nunca
  do vídeo original) e gera `briefing.md` editorial determinístico —
  **ainda sem geração de imagem**, que fica para uma entrega futura.
- `app/thumbnail_frames.py`: posições de frame igualmente espaçadas
  (cobrem início/25%/50%/75%/final do corte como caso particular do
  espaçamento uniforme); uma falha do FFmpeg aborta a extração inteira
  (diferente do `cut` — extração de frame é barata o bastante pra não
  valer a pena um resultado parcial).
- `app/thumbnail_briefing.py`: texto principal sugerido reaproveita
  `Titulo Sugerido` do CSV (já revisado por humano, nenhuma IA gera
  headline nesta fase); `participants_unknown` sempre `true` — sem
  registro de participantes ainda, nunca inventa nome; restrição extra de
  neutralidade quando `Trecho para Validar Primeiro`/`Observacoes` está
  preenchido (mesma regra já usada no `analyze`).
- `app/thumbnail_service.py`: reaproveita `select_single_chapter` e
  `build_cut_filename` (Fundação 8.0) — exige que o corte do capítulo já
  exista; idempotente por padrão (`--force` regenera); log via
  `log_operation` (`etapa="thumbnail"`).
- `--provider manual` é a única opção por enquanto — `ThumbnailProvider`
  (ABC/factory) ainda não existe, propositalmente: com um único caminho de
  código, essa abstração seria prematura.
- Saída em `thumbs/<mesmo-nome-base-do-corte>/frames/`, `briefing.md`,
  `metadata.json`.
- Validado manualmente com FFmpeg real (frames JPEG reais extraídos de um
  corte real, não mockado).

## 2026-08-15 — Entrega 8.0: Fundação compartilhada (Brand Profile, versionamento, status por capítulo)

- **Brand Profile**: novo conceito transversal, usado pela editorialização
  e thumbnail (próximas entregas) e preparado para publicação futura. Todo
  projeto grava um `"brand"` em `project.json` (nunca vazio) — `generic`
  (sem identidade de marca) ou `bussola-politica` por enquanto.
  `video-editorial init URL --brand <slug>` escolhe explicitamente; sem a
  flag, usa `VIDEO_EDITORIAL_DEFAULT_BRAND` (padrão `generic`).
- `app/brands.py` (novo) — único módulo que lê `brands/<slug>/brand.toml`.
  Cada recurso (`logo_enabled`, `intro_enabled`, `outro_enabled`,
  `cta_enabled`) só pode ficar habilitado se a configuração/asset
  correspondente existir — erro claro no carregamento, não falha
  silenciosa. `brands/generic/` e `brands/bussola-politica/` já incluídos
  (a Bússola Política ainda sem logo/intro/outro reais — só cores e CTA em
  texto, até os arquivos serem adicionados).
- `app/versioning.py` (novo) — convenção única `vNNN` (máximo existente + 1,
  sem preencher lacunas), para ser reaproveitada por editorialização e
  thumbnail sem duas implementações divergentes.
- `app/ffmpeg_utils.py` (novo) — extrai a duplicação que já existia entre
  `app/analysis.py` (`ffprobe`) e `app/cutter.py` (`ffmpeg`).
- `app/chapter_status.py` (novo) — agregador somente-leitura do estado de
  cada capítulo elegível (`03 Analise.csv` cruzado com `cortes/*.mp4`, por
  ora); `video-editorial status` passa a mostrar uma quebra por capítulo.
  Não é uma nova fonte de verdade mutável — cada etapa futura continua
  gravando seu próprio estado.
- `app/analysis.py::select_single_chapter()` (novo) — seleciona exatamente
  1 capítulo por filtro (`--chapter`/`--priority`/`--order`), erro claro
  em 0 ou >1 resultados; usado pelos comandos de capítulo único das
  próximas entregas.
- `project.json` sobe para `schema_version: 2` (novo campo `brand`);
  projetos antigos (`schema_version: 1`, sem o campo) continuam
  carregando normalmente, com `brand` assumido como `generic`.
- `requires-python` sobe para `>=3.11` — parsing de TOML via `tomllib`
  (stdlib), sem dependência nova.

## 2026-08-15 — Organização da documentação + release notes

- `PRD_Video_Editorial.md` e `PRD_Video_Editorial_plus_analyses.md` movidos
  para `docs/` (documentos "fechados" — MVP e Fase A entregues). O terceiro
  PRD (`PRD_Video_Editorial_plus_thumbnail.md`) continua na raiz, fora do
  git, por ainda não ter sido iniciado.
- Novo [docs/RELEASE_NOTES.md](RELEASE_NOTES.md): resumo em destaques por
  versão, para leitura rápida — complementa o CHANGELOG (que mantém o
  detalhe técnico por commit).
- `pyproject.toml` passa a refletir a versão atual (`0.2.0`, correspondente
  aos destaques já entregues).

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
