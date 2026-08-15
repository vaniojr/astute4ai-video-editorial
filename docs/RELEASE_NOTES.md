# Release Notes

Resumo em destaques do que cada versão trouxe, pensado para leitura rápida —
"o que dá pra fazer agora que não dava antes". Para detalhe técnico
(arquivos, commits, decisões), veja [CHANGELOG.md](CHANGELOG.md).

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
