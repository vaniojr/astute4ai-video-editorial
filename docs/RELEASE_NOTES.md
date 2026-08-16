# Release Notes

Resumo em destaques do que cada versão trouxe, pensado para leitura rápida —
"o que dá pra fazer agora que não dava antes". Para detalhe técnico
(arquivos, commits, decisões), veja [CHANGELOG.md](CHANGELOG.md).

## v0.9.1 — 2026-08-16

- **Correção de thumbnail**: achados em teste manual real — a imagem
  gerada via `--provider openai` agora sai sempre no tamanho configurado
  na marca (antes saía no tamanho fixo do `gpt-image-1`, ex. 1536×1024 em
  vez de 1280×720), e o prompt passou a instruir margens de segurança
  para o texto não ficar cortado na borda da imagem.

## v0.9.0 — 2026-08-15

- **Geração real de thumbnail**: `thumbnail --provider openai` já gera a
  imagem de verdade (via `gpt-image-1`, usando os frames reais extraídos
  como referência visual — preserva a identidade dos participantes em vez
  de inventar rostos). `--provider manual` continua sendo o padrão, sem
  custo. Pede confirmação antes de qualquer chamada paga.

## v0.8.0 — 2026-08-15

- **Cards e atribuição de fonte no vídeo renderizado**: `render` agora
  desenha os cards de contexto/subtema e a atribuição de fonte do plano
  editorial diretamente sobre o corte, aparecendo e sumindo no momento
  certo — antes só intro/CTA eram renderizados. Falta só identificar
  participantes na tela (lower thirds), que depende de um registro de
  participantes ainda não implementado.
- Corrigido também: `ffmpeg` do Homebrew (formula padrão) não tinha
  suporte a desenhar texto (`drawtext`) — documentado como trocar para o
  `ffmpeg-full`, que resolve isso sem mudar nada no projeto.

## v0.7.0 — 2026-08-15

- **Renderização do vídeo final**: novo comando `render` transforma um
  plano editorial já aprovado em `final/*.mp4` — concatena intro (texto),
  corte e CTA via FFmpeg. Precisa de uma fonte configurada na marca para
  desenhar texto na tela; sem ela, ainda gera o vídeo final (só sem os
  cards de texto). Requer um FFmpeg com suporte a `drawtext`
  (`libfreetype`) — o padrão do `brew install ffmpeg` pode não ter.
- Cards de contexto, subtemas e identificação de participante na tela
  ainda não são renderizados (o plano já os prevê; ficam para a próxima
  versão).

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
