# Release Notes

Resumo em destaques do que cada versão trouxe, pensado para leitura rápida —
"o que dá pra fazer agora que não dava antes". Para detalhe técnico
(arquivos, commits, decisões), veja [CHANGELOG.md](CHANGELOG.md).

## v0.6.0 — 2026-08-15

- **Planejamento editorial automático**: novo comando `editorialize` gera,
  via Claude, uma proposta de intro, cards de contexto e frases de
  destaque para um capítulo já cortado — pronta para revisão humana.
  Ainda não renderiza o vídeo final (próxima versão); a IA nunca decide
  timestamps, só sugere texto e posição relativa, sempre convertidos e
  verificados contra a transcrição real pelo código.

## v0.5.0 — 2026-08-15

- **Thumbnail: pronto para conectar um provider de imagem real**: a
  abstração (`ThumbnailProvider`), o versionamento (`thumbnail_v001.png`,
  `v002.png`...) e o fluxo de aprovação manual (novo comando
  `thumbnail-select`) já existem — falta só escolher e integrar um
  provider (OpenAI, Google, etc.), sem mexer no resto do pipeline.
- **Opções de headline no briefing**: `metadata.json` agora sugere até 3
  títulos candidatos, sempre reaproveitando texto já revisado por humano
  no CSV.

## v0.4.0 — 2026-08-15

- **Geração de thumbnails, primeira etapa**: novo comando `thumbnail`
  extrai frames reais do corte já gerado e monta um briefing editorial
  (tema, resumo, texto sugerido, restrições de neutralidade) — ainda sem
  gerar a imagem final, que entra numa próxima versão. Já dá pra revisar
  frames + briefing e escrever a thumbnail manualmente a partir deles.

## v0.3.0 — 2026-08-15

- **Brand Profile**: todo projeto agora tem uma identidade de marca
  explícita (`generic` ou `bussola-politica`, escolhida com
  `init URL --brand <slug>` ou por um default configurável) — base para as
  próximas features de editorialização automática e geração de thumbnails,
  que vão usar a mesma marca sem duplicar configuração.
- **`status` por capítulo**: além do resumo geral do projeto, agora mostra
  quais capítulos do `03 Analise.csv` já têm corte gerado.
- Preparação interna (sem mudança de comportamento visível): convenção
  única de versionamento de arquivos e utilitários de FFmpeg
  compartilhados, para as próximas entregas não reimplementarem cada uma a
  sua própria versão.

## v0.2.0 — 2026-08-15

- **Análise editorial automática via IA**: novo comando `analyze` gera
  `03 Analise.csv` chamando a API da Claude a partir da transcrição — antes
  esse arquivo só podia ser criado manualmente (ex.: copiando/colando num
  ChatGPT). A revisão humana continua obrigatória antes de qualquer corte
  (`cut --dry-run` + edição do CSV); o fluxo manual também continua
  funcionando normalmente.
- **Logs completos do pipeline**: todas as etapas (`init`, `download`,
  `audio`, `transcribe`, `analyze`, `cut`) agora registram início, fim e
  duração em `logs/pipeline.log` — antes só `analyze`/`cut` eram
  registradas.
- **Feedback em tempo real no terminal**: `transcribe` mostra cada trecho
  conforme é transcrito, `cut` avisa qual capítulo está cortando, e
  `download`/`audio`/`analyze` avisam quando o trabalho pesado começa —
  útil nas etapas mais demoradas do pipeline.

## v0.1.0 — 2026-08-14

- **Pipeline local completo**, ponta a ponta: a partir de uma URL do
  YouTube, criar projeto (`init`), baixar o vídeo (`download`), extrair o
  áudio (`audio`), transcrever com timestamps (`transcribe`), revisar os
  cortes propostos num CSV editável e gerar os arquivos de vídeo finais
  (`cut`).
- **Não-destrutivo por padrão**: nenhuma etapa sobrescreve o que já existe
  sem `--force`; um corte já gerado nunca é substituído automaticamente.
- **`cut --dry-run`**: valida timestamps e ações editoriais do CSV contra a
  duração real do vídeo antes de gerar qualquer arquivo, sinalizando
  capítulos ambíguos ou que precisam de revisão manual.
- **Comando `status`**: mostra o progresso de cada projeto e quais
  artefatos já existem.
