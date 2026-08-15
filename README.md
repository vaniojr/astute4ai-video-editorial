# Video Editorial

Ferramenta local para apoiar a produção editorial de vídeos longos, podcasts
e lives. Veja `docs/PRD_Video_Editorial.md` para a visão completa do produto.

Status atual: pipeline completo da Fase 1 do PRD (`init`, `download`,
`audio`, `transcribe`, `cut`, `status`), automação da análise editorial via
LLM (`analyze`, Fase A), a Fundação compartilhada (Entrega 8.0 — Brand
Profile, versionamento, status por capítulo) e o início da geração de
thumbnails (Entrega 9.1 — `thumbnail`: frames reais + briefing, ainda sem
geração de imagem). Veja
[docs/PIPELINE.md](docs/PIPELINE.md) para o passo a passo de ponta a ponta,
[docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) para os destaques de cada
versão e [docs/CHANGELOG.md](docs/CHANGELOG.md) para o histórico detalhado
do que foi entregue em cada etapa.

## Setup

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Para usar `analyze` (análise editorial automática via Claude), copie
`.env.example` para `.env` e preencha `ANTHROPIC_API_KEY` com sua chave da
[API da Anthropic](https://console.anthropic.com/). `.env` nunca é
versionado (já está no `.gitignore`); `.env.example` não tem segredo e pode
ser commitado normalmente.

## Uso

```bash
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID"
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID" --brand bussola-politica
```

Isso consulta os metadados do vídeo (via `yt-dlp`, sem baixar o arquivo),
cria um diretório único em `projetos/` no formato `YYYY-MM-DD_slug_ID` e
gera `project.json` e `01 Fonte.md`.

Todo projeto tem um **Brand Profile** (`project.json` sempre grava um
`"brand"`, nunca vazio) — `--brand` escolhe qual; sem a flag, usa o default
da aplicação (`VIDEO_EDITORIAL_DEFAULT_BRAND`, padrão `generic`). Ver seção
"Brand Profile" abaixo.

Executar novamente com a mesma URL não cria um projeto duplicado — a
ferramenta identifica o projeto existente pelo ID do vídeo e apenas informa
o caminho.

### Brand Profile

Cada profile fica em `brands/<slug>/brand.toml` (+ `brands/<slug>/assets/`
para logo/intro/outro, quando existirem). Vêm prontos:

- `generic` — sem identidade de marca, todos os recursos (logo/CTA/intro/
  outro) desligados. Default da aplicação.
- `bussola-politica` — cores e CTA configurados; logo/intro/outro ficam
  desligados até os arquivos reais serem adicionados em
  `brands/bussola-politica/assets/`.

Cada recurso (`logo_enabled`, `cta_enabled`, etc.) só pode ficar `true` se
a configuração correspondente existir — `video-editorial init` recusa a
marca (listando as disponíveis) se `--brand` não corresponder a nenhum
diretório em `brands/`. Editorialização e thumbnail (próximas entregas)
vão ler o mesmo profile via `app/brands.py`, nunca duplicando a leitura do
`brand.toml`.

```bash
uv run video-editorial download "projetos/2026-08-12_slug_ID"
```

Baixa o vídeo original (melhor qualidade disponível, vídeo+áudio combinados
via FFmpeg) para `original/video-original.mp4`. Requer FFmpeg instalado
(`brew install ffmpeg` no macOS).

Em todos os comandos, `PROJECT` aceita o nome do diretório dentro de
`projetos/`, um caminho explícito (relativo, absoluto ou `.` quando
executado de dentro do projeto), ou o `source_id` isolado do vídeo (ex.:
`video-editorial status 7xgE4ZHNWRU`, sem precisar do caminho completo).

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
uv run video-editorial analyze "projetos/2026-08-12_slug_ID"
```

Gera `03 Analise.csv` automaticamente, chamando a API da Claude com
`01 Fonte.md` + `02 Transcricao.md` (requer `ANTHROPIC_API_KEY`, ver
"Setup"). A resposta é sempre um resultado estruturado (nunca texto livre),
validado e convertido para CSV pelo próprio código — a IA nunca decide
sozinha se um timestamp é válido, e a duração de cada capítulo é sempre
calculada pelo código, nunca aceita do modelo.

- `--dry-run`: mostra provider/modelo/tamanho da transcrição/arquivo de
  saída, **sem chamar a API**.
- Pede confirmação antes de qualquer chamada real (tem custo) — use `--yes`
  para pular (automação).
- Idempotente: se `03 Analise.csv` já existe, não gera de novo — use
  `--force`.
- `--provider`/`--model` sobrescrevem a configuração padrão
  (`VIDEO_EDITORIAL_ANALYSIS_PROVIDER`, padrão `claude`;
  `VIDEO_EDITORIAL_ANALYSIS_MODEL`, padrão `claude-sonnet-5`). Só `claude`
  está implementado por enquanto — a arquitetura (`AnalysisProvider`) já
  permite adicionar outros no futuro sem mexer no restante do pipeline.
- Transcrições muito longas (acima de ~100.000 caracteres) ainda são
  enviadas numa única chamada — chunking para transcrições muito longas é
  uma evolução futura (Fase B), o `analyze --dry-run` avisa quando isso se
  aplica.
- Logo depois de escrever o CSV, `analyze` já roda a mesma validação do
  `cut --dry-run` e mostra o resultado — não precisa rodar os dois
  separadamente para ver se algum capítulo ficou `[AMBÍGUO]`/`[ERRO]`.

A **revisão humana continua obrigatória**: `analyze` só propõe o CSV, quem
decide o que de fato vira corte é `cut --dry-run` + edição manual do CSV
antes do `cut` de verdade. Se preferir não usar IA (ou a API estiver fora
do ar), o fluxo manual continua funcionando normalmente — monte
`03 Analise.csv` a partir de `01 Fonte.md`/`02 Transcricao.md`, copiando
[templates/03_Analise_exemplo.csv](templates/03_Analise_exemplo.csv) como
ponto de partida.

```bash
uv run video-editorial cut "projetos/2026-08-12_slug_ID" --dry-run
```

`cut --dry-run` lê `03 Analise.csv` (gerado por `analyze` ou editado à
mão — `cut` nunca sabe nem precisa saber a origem), valida cada linha e
mostra os cortes elegíveis, **sem gerar nenhum vídeo**.

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
ao exportar (`MM:SS:00`, `H:MM:SS:00`). O sistema sempre confia na leitura
literal H:MM:SS quando ela cabe na duração do vídeo (ex.: `00:05:00` = 5
minutos, sem ambiguidade); só quando essa leitura excede a duração é que
tenta a leitura MM:SS corrigida (ex.: `29:07:00` → `00:29:07`, já que 29h
não caberia), reportando a correção explicitamente no relatório. Só marca
`[AMBÍGUO]` (sem cortar aquele registro) quando nem a leitura H:MM:SS nem a
MM:SS cabem na duração do vídeo, ou quando não há duração de referência.

```bash
uv run video-editorial cut "projetos/2026-08-12_slug_ID"
```

Gera os cortes de todas as linhas elegíveis (`[OK]` no dry-run) em
`cortes/`, no formato `{ordem:03d}_cap{capitulo:02d}_{slug}.mp4` (o `slug`
vem de `Titulo Sugerido`, com `Tema Principal` como alternativa). Modo
padrão (`precise`): re-encoding em H.264/AAC (CRF 18, preset `medium`,
áudio 192 kbps, `faststart`), preservando resolução/aspect ratio/FPS da
fonte, sem watermark/CTA/thumbnail/legenda. `--mode fast` usa `-c copy`
(mais rápido, mas pode não iniciar exatamente no timestamp editorial — a
CLI avisa isso).

Nunca sobrescreve um corte já existente automaticamente — se o arquivo já
existir em `cortes/`, aquele registro é marcado `[PULADO]`. Linhas
`[AMBÍGUO]`/`[AVISO]`/`[ERRO]` continuam aparecendo no relatório, mas não
são cortadas; um erro do FFmpeg numa linha não interrompe as demais.

Filtros combináveis (seção 19 do PRD): `--priority A`, `--chapter 8`,
`--order 14` — funcionam tanto com `--dry-run` quanto na geração real.

```bash
uv run video-editorial thumbnail "projetos/2026-08-12_slug_ID" --chapter 8 --dry-run
uv run video-editorial thumbnail "projetos/2026-08-12_slug_ID" --chapter 8
```

Extrai 9 frames reais do corte já gerado (`cortes/`, nunca do vídeo
original — o corte já está no intervalo certo) e gera um `briefing.md`
editorial determinístico a partir da linha do `03 Analise.csv` e do Brand
Profile do projeto — **ainda sem geração de imagem** (Fase 9.1; conectar um
provider de imagem fica para uma entrega futura).

- Exige que o corte do capítulo já exista (`cortes/...`) — roda `cut`
  primeiro se faltar.
- `--dry-run`: mostra projeto/capítulo/intervalo/tema/brand/quantidade de
  frames/tamanho da thumbnail configurado, **sem chamar FFmpeg**.
- Idempotente: se `thumbs/<corte>/metadata.json` já existe, não gera de
  novo — use `--force`.
- `--provider manual` é a única opção por enquanto (a única disponível
  antes de um provider de geração de imagem existir).
- Texto principal sugerido reaproveita `Titulo Sugerido` do CSV (já
  revisado por humano) — nenhuma IA gera headline nesta fase.
  `participants_unknown` sempre `true` no `metadata.json`: sem registro de
  participantes ainda, a ferramenta nunca inventa nome.
- Saída em `thumbs/<mesmo-nome-base-do-corte>/`: `frames/frame-01.jpg`...`frame-09.jpg`,
  `briefing.md`, `metadata.json`.

## Logs e progresso

Toda execução de `init`/`download`/`audio`/`transcribe`/`analyze`/`cut`/
`thumbnail` grava em `logs/pipeline.log` (uma linha JSON por evento): timestamp, etapa,
comando, resultado (`iniciado`/`ok`/`erro`), erro (quando houver) e
`duracao_segundos`. A linha `iniciado` é gravada antes de qualquer trabalho
pesado começar — se o processo travar ou for encerrado no meio, ela já fica
registrada, mesmo sem a linha final. `status` não grava nada (é só leitura).

Etapas demoradas mostram progresso no terminal enquanto rodam:
`transcribe` imprime cada trecho conforme é transcrito, `cut` avisa qual
capítulo está cortando antes de cada arquivo, e `download`/`audio`/`analyze`
avisam quando o trabalho pesado está começando.

```bash
uv run video-editorial status "projetos/2026-08-12_slug_ID"
```

Mostra título, canal, URL, Brand Profile, o `status` atual do pipeline
(`created` → `downloaded` → `audio_ready` → `transcribed` → `analyzed` →
`cut`) e quais artefatos já existem (vídeo original, áudio, transcrição,
`03 Analise.csv`, quantidade de arquivos em `cortes/`). Se `03 Analise.csv`
já existir, mostra também uma quebra por capítulo elegível (`Manter`) —
por ora só se o corte já foi gerado; editorialização/geração de imagem da
thumbnail entram nessa mesma lista em entregas futuras.

## Testes

```bash
uv run pytest
```
