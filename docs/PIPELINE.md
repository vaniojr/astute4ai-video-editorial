# Pipeline — da URL aos cortes

Visão de ponta a ponta do fluxo local (Fase 1 do PRD). Para detalhes de
cada comando (flags, formato de saída), veja o [README](../README.md).

## 1. Criar o projeto

```bash
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID"
```

Consulta metadados (sem baixar o vídeo) e cria `projetos/YYYY-MM-DD_slug_ID/`
com `project.json` e `01 Fonte.md`.

## 2. Baixar o vídeo

```bash
uv run video-editorial download "projetos/YYYY-MM-DD_slug_ID"
```

Gera `original/video-original.mp4`. A partir daqui, `PROJECT` também pode
ser só o `source_id` do vídeo (`uv run video-editorial status VIDEO_ID`,
por exemplo) — a CLI resolve pelo nome do diretório, caminho, ou ID.

## 3. Extrair o áudio

```bash
uv run video-editorial audio "projetos/YYYY-MM-DD_slug_ID"
```

Gera `audio/audio.wav` (mono, 16 kHz) a partir do vídeo já baixado.

## 4. Transcrever

```bash
uv run video-editorial transcribe "projetos/YYYY-MM-DD_slug_ID"
```

Gera `02 Transcricao.md` e `transcricao.json`, com timestamps preservados.

## 5. Análise editorial (etapa manual)

Esta etapa **não é automatizada** nesta versão (PRD seção 14). A partir de
`01 Fonte.md` e `02 Transcricao.md`, monte `03 Analise.csv` no diretório do
projeto — copie `templates/03_Analise_exemplo.csv` como ponto de partida
para não errar o cabeçalho.

## 6. Validar (dry-run)

```bash
uv run video-editorial cut "projetos/YYYY-MM-DD_slug_ID" --dry-run
```

Lê `03 Analise.csv`, valida timestamps contra a duração real do vídeo, e
mostra os cortes elegíveis — **sem gerar nenhum vídeo**. Corrija o CSV até
o relatório não mostrar mais `[AMBÍGUO]`/`[ERRO]` nos capítulos que você
quer publicar.

## 7. Gerar os cortes

```bash
uv run video-editorial cut "projetos/YYYY-MM-DD_slug_ID"
```

Gera os arquivos em `cortes/` (`{ordem:03d}_cap{capitulo:02d}_{slug}.mp4`).
Use `--priority`/`--chapter`/`--order` para gerar só um subconjunto, e
`--mode fast` quando velocidade importar mais que precisão no corte exato.

## Verificar o estado a qualquer momento

```bash
uv run video-editorial status "projetos/YYYY-MM-DD_slug_ID"
```

Mostra o status atual do pipeline e quais artefatos já existem.

## Primeiro teste recomendado (PRD seção 35)

Antes de processar um vídeo novo, rode o pipeline inteiro com um vídeo que
você já cortou manualmente antes, e compare: metadados, duração,
transcrição, timestamps, início/fim dos cortes, nomes de arquivo. Isso
valida a ferramenta contra um resultado humano conhecido, em vez de
confiar cegamente num vídeo nunca revisado.
