# Feature — Geração Automática de Teasers Verticais

## 1. Contexto

Leia integralmente antes de qualquer implementação:

- `PRD.md`
- `docs/PIPELINE.md`
- implementação atual
- testes existentes
- `Feature_Editorializacao_Automatica.md`
- `Feature_thumbnail.md`
- configuração atual de Brand Profiles
- estrutura atual de capítulos/cortes
- serviços já existentes de FFmpeg, versionamento, providers e logs

Projeto:

```text
/Users/vaniojr/Dev/astute4ai/video-editorial
```

O pipeline atual evoluiu para:

```text
init
→ download
→ audio
→ transcribe
→ analyze
→ revisão humana
→ cut
→ editorialize
→ thumbnail
→ revisão final
→ publicação futura
```

Quero adicionar uma nova feature responsável por gerar vídeos curtos verticais a partir de cortes já aprovados.

Objetivo editorial:

```text
corte longo
→ identificar momentos fortes
→ gerar teaser vertical
→ distribuir em TikTok / Instagram Reels / Facebook Reels / YouTube Shorts
→ direcionar para o conteúdo completo
```

A feature NÃO deve ser tratada apenas como "encurtar o vídeo".

Ela deve gerar uma peça própria de distribuição, com:

- hook;
- contexto suficiente;
- trecho forte;
- legenda;
- branding;
- CTA;
- formato vertical.

---

## 2. Nome conceitual

Utilizar conceitualmente:

```text
teaser
```

Comando previsto:

```bash
video-editorial teaser PROJECT --chapter 8
```

Também prever:

```bash
video-editorial teaser PROJECT --priority A
video-editorial teaser PROJECT --all
video-editorial teaser PROJECT --dry-run
```

---

## 3. Objetivo principal

Adicionar ao Video Editorial um módulo capaz de:

1. localizar um capítulo/corte existente;
2. carregar contexto editorial;
3. analisar a transcrição correspondente ao corte;
4. identificar 1 ou mais momentos candidatos;
5. selecionar trechos que funcionem como conteúdo curto;
6. gerar `teaser_plan.json`;
7. renderizar versão 9:16;
8. adicionar headline;
9. adicionar legenda;
10. aplicar Brand Profile;
11. adicionar CTA final;
12. versionar os resultados;
13. manter revisão humana antes de publicação.

---

## 4. Pipeline específico

```text
03 Analise.csv
       +
02 Transcricao.md / transcricao.json
       +
corte aprovado
       +
Brand Profile
       ↓
TeaserPlanner
       ↓
teaser_plan.json
       ↓
validação
       ↓
TeaserRenderer
       ↓
1080x1920
       ↓
teasers/*.mp4
```

---

## 5. Relação com o corte longo

O teaser deve ser derivado de um corte já existente.

Entrada principal preferencial:

```text
cortes/*.mp4
```

ou, caso a arquitetura atual tenha definido o vídeo editorializado como artefato principal:

```text
final/*.mp4
```

Antes de implementar, analisar qual é a fonte correta no código atual.

Regra:

- usar o corte bruto/transcrição para seleção editorial;
- preservar timestamps de origem;
- utilizar o vídeo mais adequado para renderização sem degradar qualidade;
- não depender de thumbnail.

---

## 6. Não substituir o vídeo longo

O teaser NÃO substitui o corte principal.

```text
capítulo
├── vídeo longo
├── thumbnail
└── teasers
    ├── teaser 01
    ├── teaser 02
    └── teaser 03
```

Cada capítulo pode gerar zero, um ou vários teasers.

---

## 7. Formato inicial

Implementar inicialmente um único master:

```text
1080x1920
9:16
H.264
AAC
MP4
```

Esse master deve ser adequado para distribuição em:

```text
TikTok
Instagram Reels
Facebook Reels
YouTube Shorts
```

Não criar presets específicos por plataforma nesta primeira versão.

---

## 8. Duração

A duração deve ser configurável.

Faixas conceituais:

```text
short: 20–35s
medium: 35–60s
long: 60–90s
```

Configuração inicial sugerida:

```text
target_duration_seconds = 45
min_duration_seconds = 20
max_duration_seconds = 90
```

Esses valores devem ficar em configuração, não hardcoded.

---

## 9. Estratégia editorial

O teaser deve maximizar:

```text
HOOK
CONTEXTO
CURIOSIDADE
```

### Hook

Precisa parar o scroll rapidamente.

### Contexto

O trecho precisa ser compreensível isoladamente.

### Curiosidade

O teaser pode deixar espaço para o conteúdo longo responder ou aprofundar o tema.

Não usar clickbait enganoso.

---

## 10. TeaserProvider

Criar abstração:

```python
class TeaserProvider:
    def plan(self, request: TeaserRequest) -> TeaserResult:
        ...
```

Responsabilidade:

- identificar candidatos;
- sugerir hook;
- sugerir ponto inicial/final;
- explicar por que o trecho funciona;
- sugerir headline;
- sugerir CTA textual opcional.

O provider NÃO gera FFmpeg.

---

## 11. Provider inicial

Se o projeto já utiliza Claude para análise/editorialização, avaliar reutilizar:

- configuração;
- autenticação;
- logging;
- retry;
- structured output.

Manter contrato específico:

```text
TeaserProvider
```

Não reutilizar `AnalysisProvider` ou `EditorialProvider` como se fossem equivalentes.

---

## 12. Entrada do TeaserProvider

Fornecer somente:

- Tema Principal;
- Titulo Sugerido;
- Resumo;
- Pergunta Principal;
- Observacoes;
- Trecho para Validar Primeiro;
- transcrição correspondente ao corte;
- duração do corte;
- brand.

Não enviar a transcrição completa do vídeo original.

---

## 13. Saída estruturada

Usar JSON/schema.

```json
{
  "chapter": 8,
  "candidates": [
    {
      "start_seconds": 138.2,
      "end_seconds": 176.5,
      "duration_seconds": 38.3,
      "score": 0.93,
      "hook": "Como governar sem se entregar ao Centrão?",
      "headline": "SEM SE ENTREGAR AO CENTRÃO",
      "reason": "Trecho direto, compreensível e com conflito político claro."
    }
  ]
}
```

Python deve validar antes de gerar qualquer vídeo.

---

## 14. Quantidade de candidatos

Padrão inicial:

```text
3 candidatos por capítulo
```

Não renderizar automaticamente todos.

---

## 15. Seleção

Fluxo preferencial:

```text
planner
→ candidates.json
→ selecionar candidato
→ render
```

Permitir `--dry-run` para mostrar candidatos antes da renderização.

Avaliar se seleção e render devem ser comandos separados.

---

## 16. teaser_plan.json

Criar artefato intermediário.

```json
{
  "chapter": 8,
  "candidate": 1,
  "source_cut": "...",
  "source_start": 138.2,
  "source_end": 176.5,
  "hook": "...",
  "headline": "...",
  "layout": "fit_with_background",
  "captions": true,
  "cta": true,
  "brand": "bussola-politica"
}
```

Validar antes de renderização.

---

## 17. Organização de diretórios

```text
teasers/
└── 008_cap08_centrao-governabilidade/
    ├── candidates.json
    ├── briefing.md
    ├── teaser_plan.json
    ├── captions/
    │   └── teaser.ass
    ├── assets/
    ├── runs/
    │   ├── 001/
    │   └── 002/
    ├── teaser_v001.mp4
    ├── teaser_v002.mp4
    └── metadata.json
```

Reutilizar a convenção de versionamento já consolidada.

---

## 18. Estratégia visual do MVP

Não implementar crop inteligente baseado em rosto na primeira versão.

Usar layout seguro:

```text
┌──────────────────┐
│ HEADLINE         │
│                  │
│ ┌──────────────┐ │
│ │              │ │
│ │ vídeo 16:9   │ │
│ │              │ │
│ └──────────────┘ │
│                  │
│ LEGENDA          │
│                  │
│ BRAND / CTA      │
└──────────────────┘
```

Objetivo:

- preservar participantes;
- evitar cortar rostos;
- simplificar automação;
- manter consistência.

---

## 19. Background

Permitir:

```text
blurred_video
solid_color
brand_background
```

Padrão sugerido:

```text
blurred_video
```

ou a decisão visual do Brand Profile.

---

## 20. Estratégias futuras de layout

Preparar arquitetura para:

```text
smart_crop
speaker_crop
split_screen
dynamic_crop
```

Não implementar agora.

---

## 21. Headline

Headline curta no topo.

Regras:

```text
máximo 2 linhas
alto contraste
legível em tela pequena
```

Não precisa ser igual ao título do YouTube.

---

## 22. Legendas

Legendas são requisito importante.

Preferir timestamps já existentes.

Não retranscrever o áudio se `transcricao.json` já possuir granularidade suficiente.

---

## 23. Estilo de legenda

Padrão:

```text
2 linhas no máximo
centralizada
safe area
alto contraste
sem efeitos excessivos
```

Não implementar animação palavra-a-palavra no MVP.

---

## 24. Sincronização

Os timestamps da transcrição podem estar relativos ao vídeo original.

O teaser deve converter deterministicamente:

```text
timestamp original
→ timestamp no corte
→ timestamp no teaser
```

Nunca delegar essa conversão à IA.

---

## 25. CTA

CTA final curto.

Exemplo conceitual:

```text
ASSISTA AO CORTE COMPLETO
YouTube: @canal
```

ou CTA definido no Brand Profile.

Duração sugerida:

```text
3–5 segundos
```

Não hardcode canais ou handles.

---

## 26. Brand Profile

Reutilizar integralmente a fundação de branding existente.

O teaser deve herdar:

- logo;
- cores;
- fontes;
- CTA;
- estilo;
- safe areas;
- assets;
- identidade.

Não criar configuração independente para teaser.

---

## 27. Generic Profile

Se:

```text
brand = "generic"
```

o teaser deve funcionar:

- sem logo obrigatório;
- sem CTA específico;
- identidade neutra;
- source attribution opcional.

---

## 28. Source attribution

Permitir identificação discreta da fonte original.

Deve ser configurável pelo Brand Profile.

---

## 29. Conteúdo sensível

Reutilizar regras editoriais existentes.

Nunca transformar:

```text
Observacoes:
Verificar afirmação...
```

em headline factual.

Não promover automaticamente alegações sensíveis sem contexto suficiente.

---

## 30. Critério de independência

Utilizar:

```text
Independente
Precisa Contexto Anterior
```

como sinais para o planner.

Trechos não independentes não devem ser automaticamente priorizados sem contexto adicional.

---

## 31. Score

O score da IA é apenas auxiliar.

Salvar:

```text
score
reason
```

para revisão humana.

---

## 32. Renderer

Reutilizar a infraestrutura FFmpeg existente.

O renderer deve:

1. recortar o trecho;
2. montar canvas 9:16;
3. posicionar vídeo;
4. criar background;
5. aplicar headline;
6. inserir legendas;
7. aplicar branding;
8. concatenar CTA;
9. gerar MP4 final.

---

## 33. FFmpeg

Reutilizar `ffmpeg_utils.py` ou equivalente consolidado.

Validar filtros necessários.

Possíveis filtros:

```text
scale
pad
crop
boxblur/gblur
overlay
drawtext
subtitles/ass
concat
fade
```

---

## 34. Qualidade

Configuração inicial sugerida:

```text
H.264
CRF 18–20
AAC 192 kbps
faststart
1080x1920
```

Usar settings centralizados.

---

## 35. Dry run

```bash
video-editorial teaser PROJECT --chapter 8 --dry-run
```

Mostrar:

- projeto;
- capítulo;
- duração do corte;
- Brand Profile;
- provider;
- quantidade de candidatos;
- faixa de duração;
- layout;
- resolução;
- CTA;
- saída prevista.

Não chamar API paga nem renderizar vídeo final.

---

## 36. Confirmação de custo

Se o planner utilizar API paga, respeitar o padrão atual de confirmação e `--yes`.

---

## 37. Idempotência

Não sobrescrever teaser existente.

Reutilizar o sistema de versionamento atual.

---

## 38. Versionamento

Usar:

```text
v001
v002
v003
```

Não inventar outro padrão.

---

## 39. metadata.json

```json
{
  "chapter": 8,
  "candidate": 1,
  "version": 1,
  "source_cut": "...",
  "start_seconds": 138.2,
  "end_seconds": 176.5,
  "duration_seconds": 38.3,
  "brand": "bussola-politica",
  "layout": "fit_with_background",
  "provider": "claude",
  "captions": true,
  "cta": true,
  "status": "rendered"
}
```

---

## 40. Estado por capítulo

Integrar ao agregador de estado existente.

Exemplo:

```text
Capítulo 08
cut: ✓
editorial: rendered
thumbnail: selected
teaser: rendered (2)
```

Não criar uma segunda fonte global de estado.

---

## 41. Logs

Registrar:

- project;
- chapter;
- candidate;
- version;
- provider;
- render;
- duração;
- status;
- erros.

Nunca registrar secrets.

---

## 42. Segurança

Saída da IA é dado não confiável.

Não executar diretamente:

- paths;
- shell;
- comandos;
- filtros FFmpeg;

vindos do provider.

---

## 43. Testes

### Planner

Cobrir:

- corte curto;
- corte longo;
- nenhum candidato válido;
- candidato fora da duração;
- conteúdo sensível;
- `Independente = Não`;
- múltiplos candidatos.

### Timestamp

Cobrir:

```text
original
→ corte
→ teaser
```

### Renderer

Mockar FFmpeg quando possível.

Testar:

- resolução;
- layout;
- background;
- CTA;
- arquivo existente;
- versionamento;
- dry-run.

### Captions

Testar:

- início;
- fim;
- clipping;
- segmentos fora do teaser;
- UTF-8;
- acentuação.

### Provider

Usar mocks. Nunca chamar API real em testes unitários.

---

## 44. Smoke test

Após implementação, executar com um capítulo conhecido.

Validar manualmente:

1. trecho escolhido;
2. início;
3. fim;
4. headline;
5. legibilidade;
6. legenda;
7. branding;
8. áudio;
9. CTA;
10. duração.

---

## 45. Estratégia de rollout

### Fase 10.1 — Planner

Implementar:

- `TeaserProvider`;
- seleção de candidatos;
- structured output;
- `candidates.json`;
- dry-run;
- testes.

Sem renderização.

### Fase 10.2 — Renderer vertical básico

Implementar:

- recorte;
- canvas 9:16;
- vídeo central;
- background;
- headline;
- CTA;
- versionamento.

### Fase 10.3 — Legendas

Implementar:

- seleção de segmentos;
- sincronização;
- renderização;
- safe areas.

### Fase 10.4 — Refinamento

Se necessário:

- seleção automática do melhor candidato;
- múltiplos teasers;
- ajustes de layout;
- presets.

---

## 46. Fora do escopo do MVP

Não implementar agora:

- upload TikTok;
- upload Instagram;
- upload Facebook;
- upload YouTube;
- publicação;
- agendamento;
- hashtags automáticas;
- analytics;
- smart crop por rosto;
- speaker detection;
- face tracking;
- B-roll;
- stock;
- geração de imagem;
- transições complexas;
- música automática;
- A/B testing;
- feedback de performance.

---

## 47. Futuro — layouts inteligentes

Possível evolução:

```text
speaker detection
↓
face detection
↓
active speaker
↓
dynamic crop
↓
vertical inteligente
```

Não implementar no MVP.

---

## 48. Futuro — plataforma

Posteriormente:

```bash
video-editorial teaser PROJECT --chapter 8 --platform tiktok
```

com presets específicos.

Não criar presets antes de necessidade concreta.

---

## 49. Relação com monetização

Não afirmar que teaser garante monetização, alcance ou tráfego.

A feature aumenta capacidade de distribuição e reaproveitamento editorial.

---

## 50. Preparação para SaaS

A lógica deve permanecer fora da CLI.

Futuramente:

```text
POST /projects/{id}/chapters/{chapter}/teasers
```

poderá utilizar os mesmos services.

Evitar dependência da regra de negócio em:

- terminal;
- `cwd`;
- macOS;
- paths absolutos;
- prompts interativos.

---

## 51. Critérios de aceite do MVP

O MVP estará concluído quando for possível:

1. selecionar capítulo;
2. carregar transcrição;
3. gerar candidatos estruturados;
4. validar timestamps;
5. selecionar candidato;
6. gerar plano;
7. renderizar 1080x1920;
8. preservar áudio;
9. aplicar headline;
10. aplicar Brand Profile;
11. gerar CTA;
12. adicionar legenda;
13. versionar resultado;
14. executar dry-run;
15. registrar metadata/logs;
16. repetir em outro projeto sem colisão;
17. passar testes automatizados.

---

## 52. Antes de implementar

NÃO escreva código imediatamente.

Primeiro apresente:

1. estado atual relevante do projeto;
2. módulos existentes reutilizados;
3. arquivos novos;
4. arquivos modificados;
5. arquitetura proposta;
6. contrato de `TeaserProvider`;
7. schema de candidatos;
8. estratégia de seleção;
9. estratégia de timestamps;
10. estratégia de legenda;
11. estratégia de renderização 9:16;
12. estratégia de branding;
13. estrutura de outputs;
14. versionamento;
15. dry-run;
16. testes;
17. dependências adicionais;
18. riscos técnicos;
19. divisão final das fases;
20. próxima entrega recomendada.

Aguarde aprovação antes de implementar.

---

## 53. Primeira decisão de implementação

Priorizar:

```text
corte aprovado
→ IA identifica 3 candidatos
→ humano escolhe
→ render 9:16
→ headline
→ legenda
→ CTA
```

Não implementar crop inteligente, reconhecimento facial ou automação de publicação antes que esse fluxo funcione ponta a ponta.
