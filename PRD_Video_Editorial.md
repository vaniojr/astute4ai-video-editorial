# PRD — Astute4AI Video Editorial

**Produto:** Video Editorial  
**Organização:** Astute4AI  
**Fase:** Local-first / CLI  
**Status:** Planejamento inicial  
**Documento:** PRD v0.1  
**Diretório inicial:** `/Users/vaniojr/Dev/astute4ai/video-editorial`

---

## 1. Visão do Produto

O **Video Editorial** é uma ferramenta local para apoiar a produção editorial de vídeos longos, podcasts e lives.

O objetivo inicial é reduzir tarefas manuais e repetitivas do fluxo:

1. registrar a fonte;
2. baixar o vídeo;
3. preparar o áudio;
4. transcrever;
5. produzir uma análise editorial estruturada;
6. validar capítulos/cortes;
7. gerar automaticamente os arquivos dos cortes;
8. manter todos os artefatos organizados e rastreáveis.

A primeira implementação será executada localmente via CLI, utilizando principalmente Python, `yt-dlp`, FFmpeg e Whisper/faster-whisper.

A arquitetura deve, porém, evitar acoplamentos desnecessários ao ambiente local para permitir uma evolução posterior para aplicação web/SaaS.

O primeiro caso de uso será a operação editorial de canais de conteúdo, mas o produto não deve possuir regras específicas de uma única marca ou nicho.

---

## 2. Problema

O processo atual de transformar um vídeo longo em cortes publicáveis envolve diversas etapas manuais:

```text
Encontrar vídeo
→ registrar informações da fonte
→ obter/transcrever conteúdo
→ analisar a transcrição
→ identificar capítulos
→ registrar timestamps
→ validar cortes
→ abrir editor
→ localizar timestamps novamente
→ exportar cada trecho
→ organizar arquivos
```

Os principais problemas são:

- dependência da transcrição disponibilizada pelo YouTube;
- necessidade de manipular vídeos longos manualmente;
- repetição de informações entre ferramentas;
- risco de erros nos timestamps;
- arquivos espalhados ou sobrescritos;
- dificuldade de reproduzir o processamento;
- falta de rastreabilidade entre fonte, transcrição, análise e corte;
- esforço elevado para processar novos vídeos;
- pouca reutilização do processo entre diferentes canais.

---

## 3. Objetivo

Criar um pipeline local e reutilizável no qual um novo projeto possa ser iniciado a partir de uma URL e seus artefatos sejam gerenciados de forma padronizada.

Visão desejada:

```text
URL
 ↓
Projeto
 ↓
Fonte
 ↓
Download
 ↓
Áudio
 ↓
Transcrição
 ↓
Análise editorial
 ↓
Validação humana
 ↓
Cortes
```

O operador deve conseguir repetir o processo para dezenas ou centenas de vídeos sem sobrescrever projetos anteriores.

---

## 4. Princípios

### 4.1 Local-first

A primeira versão deve funcionar integralmente no computador do usuário.

Não exigir:

- servidor;
- banco de dados;
- frontend;
- fila;
- Redis;
- storage externo.

---

### 4.2 Automação com controle humano

Automatizar tarefas mecânicas.

Manter decisão humana em tarefas editoriais importantes.

Exemplos:

**Automático:**
- metadados;
- criação de diretórios;
- download;
- extração de áudio;
- transcrição;
- interpretação validada de timestamps;
- geração física dos cortes.

**Humano:**
- aprovação editorial;
- seleção final de cortes;
- revisão de afirmações sensíveis;
- decisão de publicação.

---

### 4.3 Não destrutivo

O sistema nunca deve:

- alterar o vídeo original;
- apagar automaticamente arquivos fonte;
- sobrescrever cortes sem confirmação;
- substituir uma análise existente silenciosamente.

---

### 4.4 Rastreabilidade

Todo corte deve ser rastreável até:

```text
corte
→ capítulo
→ análise
→ transcrição
→ vídeo original
→ URL original
```

---

### 4.5 Preparado para SaaS

A CLI deve ser apenas uma interface.

A lógica principal deve permanecer em módulos reutilizáveis.

Evitar implementar regras de negócio diretamente em shell scripts.

---

# 5. Escopo do MVP Local

## 5.1 Criação de projeto

Comando conceitual:

```bash
./bussola iniciar "URL"
```

O nome da CLI poderá mudar durante a implementação. O domínio interno do produto deve permanecer genérico (`video-editorial`).

A ferramenta deve:

1. validar a URL;
2. consultar metadados via `yt-dlp`;
3. obter o ID do vídeo;
4. detectar título;
5. detectar canal;
6. detectar data quando disponível;
7. detectar duração;
8. criar slug;
9. verificar se o vídeo já possui projeto;
10. criar diretório único;
11. criar `project.json`;
12. criar `01 Fonte.md`.

---

# 6. Identidade do Projeto

Cada vídeo deve possuir um identificador único baseado prioritariamente no ID da plataforma.

Para YouTube:

```text
youtube_id
```

Padrão de diretório:

```text
YYYY-MM-DD_slug_ID
```

Exemplo:

```text
2026-08-12_podcast-3-irmaos_7xgE4ZHNWRU
```

O ID do YouTube deve impedir colisões mesmo quando existirem títulos iguais.

---

# 7. Estrutura de Diretórios

Estrutura inicial do repositório:

```text
video-editorial/
├── app/
│   ├── __init__.py
│   ├── project.py
│   ├── metadata.py
│   ├── downloader.py
│   ├── audio.py
│   ├── transcriber.py
│   ├── analysis.py
│   ├── timestamps.py
│   └── cutter.py
│
├── cli/
│   ├── __init__.py
│   └── main.py
│
├── templates/
│   └── fonte.md
│
├── prompts/
│   └── README.md
│
├── projetos/
│
├── tests/
│
├── docs/
│
├── .gitignore
├── pyproject.toml
├── README.md
└── PRD.md
```

A estrutura poderá ser ajustada durante a implementação se houver justificativa técnica.

---

# 8. Estrutura de Cada Projeto

```text
projetos/
└── YYYY-MM-DD_slug_ID/
    ├── project.json
    ├── 01 Fonte.md
    ├── 02 Transcricao.md
    ├── 03 Analise.csv
    │
    ├── original/
    │   └── video-original.mp4
    │
    ├── audio/
    │   └── audio.wav
    │
    ├── cortes/
    │
    ├── thumbs/
    │
    ├── publicados/
    │
    └── logs/
```

Nem todos os arquivos precisam existir imediatamente após `iniciar`.

Os diretórios podem ser criados antecipadamente ou sob demanda.

---

# 9. project.json

Arquivo interno de estado e identificação.

Exemplo:

```json
{
  "schema_version": 1,
  "platform": "youtube",
  "source_id": "7xgE4ZHNWRU",
  "source_url": "https://www.youtube.com/watch?v=7xgE4ZHNWRU",
  "title": "Renan Santos Kim Kataguiri e Renato Battista - Podcast 3 Irmãos #1033",
  "channel": "Podcast 3 Irmãos",
  "published_at": "2026-08-12",
  "duration_seconds": 6300,
  "slug": "podcast-3-irmaos",
  "created_at": "2026-08-14T18:00:00-03:00",
  "status": "created"
}
```

`project.json` deve ser tratado como estado da aplicação.

`01 Fonte.md` deve ser tratado como documento legível/editável pelo operador.

---

# 10. 01 Fonte.md

Documento de metadados editoriais.

Formato esperado:

```markdown
# Informações da fonte

Título original:
...

Canal:
...

URL:
...

ID:
...

Participantes:
- ...

Formato:
...

Data:
YYYY-MM-DD

Duração:
HH:MM:SS

Observações:
...
```

Campos que puderem ser obtidos automaticamente devem ser preenchidos durante a criação.

Campos editoriais podem permanecer vazios.

Exemplos:

```text
Participantes
Formato
Observações
```

Não sobrescrever conteúdo preenchido manualmente em execuções posteriores.

---

# 11. Download

Comando conceitual:

```bash
video-editorial download PROJETO
```

Responsabilidade:

- localizar projeto;
- ler URL de origem;
- baixar vídeo usando `yt-dlp`;
- selecionar qualidade adequada;
- combinar áudio/vídeo quando necessário;
- produzir arquivo final compatível com FFmpeg.

Destino:

```text
original/video-original.mp4
```

O download deve ser idempotente.

Se o arquivo já existir:

```text
Arquivo original já existe.
Nenhum download realizado.
```

Permitir posteriormente opção explícita:

```text
--force
```

---

# 12. Áudio

O áudio para transcrição deve ser derivado do vídeo já baixado.

Não baixar novamente o áudio do YouTube.

Fluxo:

```text
video-original.mp4
      ↓
FFmpeg
      ↓
audio.wav
```

Formato inicial recomendado:

```text
mono
16 kHz
WAV
```

Exemplo técnico:

```bash
ffmpeg \
  -i video-original.mp4 \
  -vn \
  -ac 1 \
  -ar 16000 \
  audio.wav
```

Destino:

```text
audio/audio.wav
```

O arquivo deve ser considerado derivado e descartável.

---

# 13. Transcrição

Comando conceitual:

```bash
video-editorial transcribe PROJETO
```

Primeira alternativa técnica:

```text
faster-whisper
```

A implementação deve permitir futura substituição do motor.

Interface conceitual:

```python
class TranscriptionProvider:
    def transcribe(self, audio_path):
        ...
```

Possíveis implementações futuras:

```text
FasterWhisperProvider
OpenAIProvider
ExternalProvider
```

A transcrição precisa preservar timestamps.

Saídas desejadas:

```text
02 Transcricao.md
```

e, se útil:

```text
transcricao.srt
transcricao.json
```

O JSON pode preservar informação estruturada por segmento para processamento posterior.

---

# 14. Análise Editorial

A análise editorial transforma a transcrição em capítulos candidatos.

Entrada:

```text
01 Fonte.md
02 Transcricao.md
```

Saída principal:

```text
03 Analise.csv
```

O processo inicial poderá continuar utilizando Claude externamente/manual no VS Code.

A primeira versão NÃO precisa integrar uma API de LLM.

Entretanto, o software deve reservar uma camada:

```text
analysis.py
```

para futura automação.

---

# 15. Estrutura Mínima do CSV

O sistema deve reconhecer inicialmente:

```text
Ordem Publicacao
Prioridade
Capitulo
Bloco Editorial
Acao Editorial
Timestamp Inicial
Timestamp Final
Duracao
Tema Principal
Titulo Sugerido
Palavra-chave Principal
Trecho para Validar Primeiro
Resumo
Pergunta Principal
Independente
Precisa Contexto Anterior
Grau de Confianca
Observacoes
```

Os nomes reais encontrados no arquivo devem ser validados.

Não depender da posição das colunas.

---

# 16. Ação Editorial

Valores como:

```text
Manter
```

podem ser elegíveis para corte.

Valores equivalentes a:

```text
Descartar
Não publicar
Arquivar
```

devem ser ignorados.

Ações que impliquem edição especial:

```text
Unir
Separar
Transformar em teaser
Revisar
```

não devem ser executadas automaticamente no MVP.

Devem gerar aviso.

---

# 17. Timestamps

Tratamento de timestamps é requisito crítico.

Formatos possíveis:

```text
29:07
01:12:09
29:07:00
1:12:09:00
```

Planilhas podem transformar valores originalmente em `MM:SS`.

Exemplo:

```text
29:07
```

pode ser exportado como:

```text
29:07:00
```

O sistema NÃO deve interpretar automaticamente esse valor como 29 horas se isso for incompatível com o vídeo.

A validação deve considerar:

- duração total;
- timestamp inicial;
- timestamp final;
- coluna duração;
- consistência entre registros.

Em caso de ambiguidade:

```text
AMBÍGUO
```

e interromper o corte daquele registro.

Nunca adivinhar silenciosamente.

---

# 18. Dry Run

Antes de gerar cortes:

```bash
video-editorial cut PROJETO --dry-run
```

Saída esperada:

```text
Projeto:
2026-08-12_podcast-3-irmaos_7xgE4ZHNWRU

Vídeo:
original/video-original.mp4

Duração:
01:45:03

CSV:
03 Analise.csv

Cortes elegíveis:
6

[OK] Capítulo 08
00:29:07 → 00:37:22
Duração: 00:08:15

[OK] Capítulo 14
01:12:09 → 01:20:22
Duração: 00:08:13
```

Nenhum vídeo deve ser gerado.

---

# 19. Geração dos Cortes

Comando conceitual:

```bash
video-editorial cut PROJETO
```

Filtros:

```bash
--priority A
--chapter 8
--order 14
```

Modo padrão:

```text
preciso
```

FFmpeg com re-encoding.

Formato:

```text
MP4
H.264
AAC
```

Configuração inicial:

```text
CRF 18
preset medium
AAC 192 kbps
faststart
```

Preservar:

- resolução;
- aspect ratio;
- FPS.

Não adicionar:

- watermark;
- CTA;
- thumbnail;
- legenda embutida.

---

# 20. Modo Rápido

Opcional:

```bash
--mode fast
```

Pode usar:

```text
-c copy
```

A interface deve avisar:

```text
Modo rápido utiliza keyframes e pode não iniciar exatamente
no timestamp editorial.
```

O modo preciso permanece padrão.

---

# 21. Nome dos Cortes

Formato:

```text
{ordem:03d}_cap{capitulo:02d}_{slug}.mp4
```

Exemplo:

```text
008_cap08_nao-vou-ser-usado-pelo-centrao.mp4
014_cap14_debates-presidenciais.mp4
```

Regras:

- minúsculas;
- sem acentos;
- espaços → hífen;
- remover caracteres incompatíveis;
- tamanho máximo razoável;
- não sobrescrever automaticamente.

---

# 22. Prevenção de Duplicidade

Ao iniciar um projeto, pesquisar por `source_id`.

Se já existir:

```text
Projeto já existente:

projetos/2026-08-12_podcast-3-irmaos_7xgE4ZHNWRU
```

Não criar duplicata automaticamente.

Uma versão futura poderá suportar:

```bash
--new-version
```

gerando:

```text
..._v2
```

---

# 23. Estado do Pipeline

Estados iniciais possíveis:

```text
created
downloaded
audio_ready
transcribed
analyzed
validated
cut
published
```

O estado deve refletir o estágio mais avançado efetivamente concluído.

Não marcar etapas apenas porque arquivos foram solicitados.

---

# 24. CLI Desejada

Visão de longo prazo da CLI:

```bash
video-editorial init URL

video-editorial download PROJECT

video-editorial audio PROJECT

video-editorial transcribe PROJECT

video-editorial analyze PROJECT

video-editorial cut PROJECT --dry-run

video-editorial cut PROJECT --priority A

video-editorial status PROJECT
```

Atalho futuro:

```bash
video-editorial process URL
```

Não implementar o comando completo antes das etapas individuais estarem estáveis.

---

# 25. Seleção de Projeto

Para evitar digitar nomes longos, a CLI deverá futuramente aceitar:

```text
source ID
slug
path
```

Exemplo:

```bash
video-editorial status 7xgE4ZHNWRU
```

Também pode existir conceito de projeto atual:

```bash
cd projetos/2026-08-12_.../
video-editorial status .
```

---

# 26. Logs

Cada projeto deve possuir:

```text
logs/
```

Registrar pelo menos:

```text
timestamp
etapa
comando
resultado
erro
```

Nunca registrar:

- tokens;
- credenciais;
- cookies;
- segredos.

---

# 27. Git

Arquivos de código e metadados devem ser versionáveis.

Não versionar arquivos grandes derivados.

`.gitignore` inicial:

```gitignore
# Python
.venv/
__pycache__/
*.pyc

# macOS
.DS_Store

# Secrets
.env
*.cookies.txt

# Media
projetos/*/original/*
projetos/*/audio/*
projetos/*/cortes/*
projetos/*/logs/*

*.mp4
*.mov
*.mkv
*.webm
*.wav
*.mp3
```

Avaliar separadamente se thumbnails devem ser versionadas.

---

# 28. Dependências Externas

Inicialmente:

```text
Python 3
yt-dlp
FFmpeg / ffprobe
faster-whisper
```

macOS:

```bash
brew install ffmpeg yt-dlp
```

Dependências Python devem ser declaradas no `pyproject.toml`.

---

# 29. Configuração

Evitar constantes espalhadas.

Preparar configuração central para:

```text
diretório de projetos
modelo Whisper
idioma padrão
CRF
preset FFmpeg
bitrate de áudio
formato de saída
```

Inicialmente pode ser arquivo local:

```text
config.toml
```

ou configuração Python tipada.

Não criar complexidade desnecessária no MVP.

---

# 30. Tratamento de Erros

Mensagens devem ser acionáveis.

Ruim:

```text
Process failed.
```

Bom:

```text
FFmpeg não foi encontrado.

Instale no macOS:

brew install ffmpeg
```

Outro exemplo:

```text
O timestamp 29:07:00 é ambíguo.

Duração total do vídeo: 01:43:20
Valor original: 29:07:00
Possível interpretação: 00:29:07

Nenhum corte foi realizado.
```

---

# 31. Testes

Priorizar testes para componentes que podem provocar erro silencioso.

### Obrigatórios

#### Timestamp parser

Cobrir:

```text
29:07
01:12:09
29:07:00
1:12:09:00
```

#### Slug

Cobrir:

```text
acentos
aspas
pontuação
nomes longos
caracteres especiais
```

#### Project ID

Garantir prevenção de duplicidade.

#### CSV

Garantir leitura UTF-8 e UTF-8-SIG.

#### Cutter

Testar geração do comando FFmpeg sem executar mídia real quando possível.

---

# 32. Fora do Escopo do MVP

Não implementar inicialmente:

- frontend web;
- autenticação;
- usuários;
- banco PostgreSQL;
- Supabase;
- Vercel;
- pagamentos;
- upload automático para YouTube;
- Instagram;
- Facebook;
- TikTok;
- geração automática de thumbnails;
- geração automática de Shorts;
- edição gráfica;
- CTA automático;
- publicação;
- agendamento;
- analytics;
- monetização;
- colaboração multiusuário.

Esses itens pertencem a fases posteriores.

---

# 33. Evolução Prevista

## Fase 1 — CLI local

```text
URL
→ projeto
→ download
→ áudio
→ transcrição
→ CSV
→ cortes
```

## Fase 2 — Automação editorial

```text
transcrição
→ LLM
→ capítulos
→ classificação
→ validação
→ cortes
```

## Fase 3 — Interface local/web

```text
Projetos
Transcrição
Timeline
Capítulos
Preview
Aprovação
```

## Fase 4 — SaaS

Possível arquitetura:

```text
Frontend
   ↓
API
   ↓
PostgreSQL
   ↓
Job Queue
   ↓
Workers
   ├── download
   ├── transcription
   ├── AI analysis
   └── rendering
   ↓
Object Storage
```

A arquitetura local não precisa implementar esses componentes agora, apenas evitar decisões que impeçam a evolução.

---

# 34. Critérios de Sucesso do MVP

O MVP estará funcional quando for possível:

1. informar uma URL válida do YouTube;
2. criar automaticamente um projeto único;
3. gerar `project.json`;
4. gerar `01 Fonte.md`;
5. baixar o vídeo;
6. gerar áudio adequado à transcrição;
7. transcrever com timestamps;
8. receber um `03 Analise.csv`;
9. validar os timestamps;
10. executar dry-run;
11. selecionar prioridade/capítulo;
12. gerar cortes MP4 precisos;
13. processar outro vídeo sem afetar o anterior.

---

# 35. Primeiro Caso de Teste

Utilizar inicialmente um vídeo já processado manualmente.

Isso permite comparar:

```text
processo manual
vs.
processo automatizado
```

Validar especialmente:

- metadados;
- duração;
- transcrição;
- timestamps;
- início/fim dos cortes;
- nomes;
- organização dos arquivos.

Não começar os testes com um vídeo desconhecido.

---

# 36. Ordem Recomendada de Implementação

Não implementar tudo simultaneamente.

### Entrega 1 — Fundação

```text
estrutura Python
CLI
configuração
modelo Project
slug
project.json
criação de diretórios
01 Fonte.md
```

### Entrega 2 — Download

```text
yt-dlp
metadados
download
idempotência
```

### Entrega 3 — Áudio

```text
ffprobe
FFmpeg
extração WAV
```

### Entrega 4 — Transcrição

```text
faster-whisper
timestamps
02 Transcricao.md
```

### Entrega 5 — CSV

```text
leitura
encoding
parser de timestamps
validação
dry-run
```

### Entrega 6 — Cortes

```text
FFmpeg
filtros
nomes
logs
relatório
```

### Entrega 7 — Refinamento

```text
testes
tratamento de erros
documentação
CLI consolidada
```

Cada entrega deve estar funcional antes da próxima.

---

# 37. Diretriz para o Agente de Código

Ao utilizar este PRD com Claude Code, Codex ou outro agente:

1. Leia este PRD integralmente antes de alterar arquivos.
2. Não implemente funcionalidades de fases futuras sem solicitação.
3. Antes de cada entrega, apresente o plano de arquivos que serão criados/alterados.
4. Faça alterações pequenas e verificáveis.
5. Não execute operações destrutivas.
6. Não apague arquivos do usuário.
7. Não sobrescreva mídia existente.
8. Crie testes para regras críticas.
9. Execute os testes após mudanças relevantes.
10. Atualize README quando comandos públicos mudarem.
11. Não introduza serviços cloud no MVP.
12. Prefira abstrações simples a arquiteturas prematuras.
13. Quando houver ambiguidade funcional relevante, pergunte antes de decidir.
14. Preserve compatibilidade com macOS Apple Silicon.
15. Considere futura execução Linux, evitando dependências exclusivas do macOS na lógica de negócio.

---

# 38. Primeira Solicitação ao Agente

Após adicionar este PRD ao repositório, a primeira solicitação recomendada é:

> Leia integralmente o `PRD.md`. Não implemente o pipeline completo. Analise o repositório vazio e proponha o plano técnico apenas para a **Entrega 1 — Fundação**, incluindo estrutura de diretórios, dependências Python, CLI, modelo de projeto, geração de `project.json`, criação dos diretórios do projeto e geração do `01 Fonte.md`. Antes de escrever código, apresente o plano de implementação e decisões técnicas para aprovação.

Isso evita que o agente tente implementar download, Whisper, FFmpeg, análise e cortes em uma única rodada.
