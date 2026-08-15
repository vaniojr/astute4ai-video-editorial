# Pipeline — da URL à thumbnail

Visão de ponta a ponta do fluxo local: Fase 1 do PRD (download → corte),
automação da análise editorial via LLM, planejamento/renderização
editorial e geração de thumbnail. Para detalhes de cada comando (flags,
formato de saída), veja o [README](../README.md).

```
init → download → audio → transcribe → analyze → cut
                                                    ├─→ editorialize → render
                                                    └─→ thumbnail → thumbnail-select
```

`editorialize`/`render` e `thumbnail`/`thumbnail-select` são ramos
paralelos a partir do `cut` — não dependem um do outro (a thumbnail usa o
corte bruto como referência visual, não o vídeo editorializado).

## 1. Criar o projeto

```bash
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID"
uv run video-editorial init "https://www.youtube.com/watch?v=VIDEO_ID" --brand bussola-politica
```

Consulta metadados (sem baixar o vídeo) e cria `projetos/YYYY-MM-DD_slug_ID/`
com `project.json` e `01 Fonte.md`. Todo projeto tem um **Brand Profile**
(`--brand`, padrão `generic` se omitido) — ver seção "Brand Profile" do
README para o que cada marca pode configurar (cores, fonte, CTA).

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

## 5. Análise editorial

```bash
uv run video-editorial analyze "projetos/YYYY-MM-DD_slug_ID"
```

Gera `03 Analise.csv` automaticamente via API da Claude, a partir de
`01 Fonte.md` + `02 Transcricao.md` (requer `ANTHROPIC_API_KEY` em `.env`
— veja o README). Roda `--dry-run` primeiro se quiser ver o plano
(provider, modelo, tamanho da transcrição) sem gastar nada; pede
confirmação antes de qualquer chamada real, com custo.

**Revisão humana continua obrigatória** — `analyze` só propõe o CSV, quem
decide o que publicar é a revisão manual do arquivo antes do corte.

### Alternativa: análise manual

Se preferir não usar IA (ou a API estiver indisponível), monte
`03 Analise.csv` você mesmo a partir de `01 Fonte.md`/`02 Transcricao.md`
— copie `templates/03_Analise_exemplo.csv` como ponto de partida para não
errar o cabeçalho. `cut` não sabe (nem precisa saber) se o CSV foi gerado
por IA ou digitado à mão.

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

A partir daqui, `editorialize`/`render` e `thumbnail`/`thumbnail-select`
são independentes entre si — pode fazer só um dos dois, os dois, ou
nenhum (o corte em `cortes/` já é publicável sozinho).

## 8. Planejar a editorialização (opcional)

```bash
uv run video-editorial editorialize "projetos/YYYY-MM-DD_slug_ID" --chapter 8 --dry-run
uv run video-editorial editorialize "projetos/YYYY-MM-DD_slug_ID" --chapter 8
```

Gera `editorial_plan_vNNN.json` (intro curta, cards de contexto/subtema,
frases de destaque) via Claude, a partir do corte já gerado + só o trecho
correspondente da transcrição. **Não renderiza vídeo** — revise o plano
(`editorial/<corte>/editorial_plan_vNNN.json`) antes de rodar `render`.
`--dry-run` primeiro se quiser ver o que seria enviado sem gastar nada;
pede confirmação antes de qualquer chamada real.

## 9. Renderizar o vídeo final (opcional, depende do passo 8)

```bash
uv run video-editorial render "projetos/YYYY-MM-DD_slug_ID" --chapter 8 --dry-run
uv run video-editorial render "projetos/YYYY-MM-DD_slug_ID" --chapter 8
```

Gera `final/<corte>_vNNN.mp4`: intro → corte (com cards e atribuição de
fonte sobrepostos) → CTA, via FFmpeg. Intro/CTA/cards em texto exigem uma
fonte configurada na marca (`brand.assets.primary_font`) — sem fonte, o
comando ainda gera o `final/*.mp4` (só sem os elementos de texto). Sem
custo (roda local); `--force` gera uma nova versão sem sobrescrever.

## 10. Gerar a thumbnail (opcional, independente do passo 8/9)

```bash
uv run video-editorial thumbnail "projetos/YYYY-MM-DD_slug_ID" --chapter 8 --dry-run
uv run video-editorial thumbnail "projetos/YYYY-MM-DD_slug_ID" --chapter 8
```

Extrai 9 frames reais do corte + gera `briefing.md` (tema, resumo, opções
de headline). Com `--provider manual` (padrão, sem custo), fica só nisso
— frames e briefing prontos para montar a thumbnail à mão. Com
`--provider openai` (requer `OPENAI_API_KEY` em `.env`), gera a imagem de
verdade via `gpt-image-1`, usando os frames reais como referência visual
(preserva a identidade dos participantes); pede confirmação antes da
chamada paga.

```bash
uv run video-editorial thumbnail-select "projetos/YYYY-MM-DD_slug_ID" --chapter 8 --version 1
```

Aprova manualmente uma das versões geradas (`selected.png`) — nunca
escolhido automaticamente.

## Verificar o estado a qualquer momento

```bash
uv run video-editorial status "projetos/YYYY-MM-DD_slug_ID"
```

Mostra o status geral do projeto e, se `03 Analise.csv` já existir, uma
quebra por capítulo elegível (se o corte já foi gerado, se já existe um
plano editorial).

## Primeiro teste recomendado (PRD seção 35)

Antes de processar um vídeo novo, rode o pipeline inteiro com um vídeo que
você já cortou manualmente antes, e compare: metadados, duração,
transcrição, timestamps, início/fim dos cortes, nomes de arquivo. Isso
valida a ferramenta contra um resultado humano conhecido, em vez de
confiar cegamente num vídeo nunca revisado.
