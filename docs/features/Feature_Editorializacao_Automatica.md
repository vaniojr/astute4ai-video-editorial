# Feature — Editorialização Automática dos Cortes

## 1. Contexto

Leia integralmente o `PRD.md`, o `docs/PIPELINE.md`, a implementação atual do projeto e os testes antes de modificar qualquer arquivo.

Projeto:

`/Users/vaniojr/Dev/astute4ai/video-editorial`

Pipeline atual:

```text
URL
→ projeto
→ download
→ áudio
→ transcrição
→ análise editorial
→ 03 Analise.csv
→ revisão humana
→ cortes
→ thumbnail
→ publicação
```

Adicionar uma nova etapa:

```text
corte bruto
→ editorialização
→ vídeo final
→ thumbnail
→ publicação
```

O objetivo é adicionar contexto, identidade e organização editorial própria ao corte antes da publicação.

---

## 2. Objetivo

Adicionar um módulo responsável por transformar um corte bruto em uma peça editorial final.

Entradas:

- `cortes/*.mp4`
- `03 Analise.csv`
- `01 Fonte.md`
- `02 Transcricao.md`
- `project.json`
- configuração da marca

Saída:

- `final/*.mp4`

Funcionalidades iniciais:

1. intro editorial;
2. identificação da fonte;
3. lower thirds;
4. cards de contexto/subtema;
5. destaques de frases;
6. CTA final;
7. branding consistente;
8. artefatos intermediários auditáveis.

---

## 3. Princípio fundamental

O módulo deve adicionar valor editorial real.

Evitar que o objetivo principal seja apenas:

- zoom;
- bordas;
- crop artificial;
- filtros;
- efeitos;
- mudança de velocidade.

O foco deve ser:

- contextualização;
- organização;
- identificação;
- explicação;
- atribuição de fonte;
- narrativa editorial.

---

## 4. CLI

Adicionar conceitualmente:

```bash
video-editorial editorialize PROJECT --chapter 8
video-editorial editorialize PROJECT --priority A
video-editorial editorialize PROJECT --all
video-editorial editorialize PROJECT --dry-run
```

---

## 5. Arquitetura

Não concentrar a lógica em um único script FFmpeg.

Separar responsabilidades:

```text
app/
└── editorial/
    ├── __init__.py
    ├── models.py
    ├── planner.py
    ├── service.py
    ├── timeline.py
    ├── renderer.py
    ├── assets.py
    ├── branding.py
    └── providers/
```

Adaptar à arquitetura atual se necessário.

---

## 6. Fluxo

```text
03 Analise.csv
+ 02 Transcricao.md
+ 01 Fonte.md
+ corte bruto
↓
EditorialPlanner
↓
editorial_plan.json
↓
validação
↓
assets
↓
Renderer
↓
video-final.mp4
```

---

## 7. editorial_plan.json

A IA não deve gerar comandos FFmpeg.

Gerar primeiro um plano estruturado:

```json
{
  "chapter": 8,
  "cut_file": "008_cap08_centrao-governabilidade.mp4",
  "intro": {},
  "lower_thirds": [],
  "context_cards": [],
  "highlights": [],
  "source_attribution": {},
  "cta": {},
  "branding": {},
  "render": {}
}
```

Depois:

```text
editorial_plan.json
→ validação Python
→ Renderer
```

---

## 8. Organização por capítulo

```text
editorial/
└── 008_cap08_centrao-governabilidade/
    ├── editorial_plan.json
    ├── briefing.md
    ├── assets/
    │   ├── intro/
    │   ├── cards/
    │   ├── lower-thirds/
    │   └── audio/
    ├── preview/
    ├── logs/
    └── metadata.json
```

Vídeo final:

```text
final/
└── 008_cap08_centrao-governabilidade.mp4
```

Nunca sobrescrever o corte bruto.

---

## 9. Intro editorial

Adicionar intro curta antes do corte.

Duração configurável, inicialmente entre 8 e 15 segundos.

Exemplo:

```text
Neste trecho, Renan Santos explica como pretende negociar
com o Centrão caso seja eleito, sem entregar o controle do governo.
```

A intro não deve inventar fatos ou converter alegações em fatos.

Modos previstos:

```text
text_only
voice_and_text
disabled
```

Implementar primeiro `text_only`.

---

## 10. Narração futura

Se houver TTS, abstrair:

```python
class VoiceProvider:
    def synthesize(self, text: str) -> Path:
        ...
```

Não imitar a voz dos participantes.

---

## 11. Lower thirds

Inserir identificação visual quando os participantes forem conhecidos.

Exemplo:

```text
Renan Santos
```

Cargo só deve aparecer se vier de fonte validada/configurada.

Não inferir cargo atual silenciosamente.

---

## 12. Cards de contexto

Permitir poucos cards por corte.

Padrão inicial:

```text
0 a 4 cards
```

Exemplos:

```text
CONTEXTO
O debate trata da formação de maioria no Congresso.
```

```text
TEMA
Governabilidade e relação com o Centrão
```

```text
FONTE
Podcast 3 Irmãos #1033
```

---

## 13. Cards de subtema

Para cortes longos, permitir transições com subtemas:

```text
1. Como formar maioria?
2. Relação com o Centrão
3. Composição ministerial
4. Investigações e emendas
```

Não recortar novamente o vídeo automaticamente.

---

## 14. Destaques de frases

Permitir destacar frases existentes na transcrição.

Exemplo:

```text
"O Centrão deve ser usado, não usar o governo."
```

Salvar com timestamps relativos ao corte.

Nunca inventar quotes.

---

## 15. Legendas

Preparar suporte:

```text
none
normal
highlight_only
full
```

Não usar estilo TikTok agressivo como padrão.

---

## 16. CTA final

Usar CTA genérico por marca.

Exemplo:

```text
BÚSSOLA POLÍTICA
Curta • Comente • Compartilhe • Inscreva-se
```

Não incluir detalhes específicos do corte.

---

## 17. Fonte original

Adicionar atribuição discreta:

```text
Fonte original:
Podcast 3 Irmãos #1033
```

---

## 18. Branding

Não hardcode Bússola Política.

Estrutura conceitual:

```text
brands/
└── bussola-politica/
    ├── brand.toml
    ├── logo.png
    ├── intro/
    ├── outro/
    └── assets/
```

Exemplo:

```toml
name = "Bússola Política"
primary = "#F5C400"
background = "#090909"
text = "#FFFFFF"
accent = "#C92020"

intro_enabled = true
cta_enabled = true
source_attribution = true
```

---

## 19. Resolução e safe area

Preservar:

- resolução;
- aspect ratio;
- FPS.

Não converter automaticamente 16:9 para 9:16 ou 1:1.

Manter texto, logo e lower thirds afastados das bordas.

---

## 20. Renderer

Usar FFmpeg no MVP.

Receber:

```text
vídeo
editorial_plan
assets
configuração
```

Produzir:

```text
video-final.mp4
```

Usar `subprocess.run([...], shell=False)`.

---

## 21. Composição

A implementação pode gerar:

```text
intro.mp4
+
corte-bruto.mp4
+
cta.mp4
↓
video-final.mp4
```

Garantir compatibilidade de codec, resolução, FPS e áudio.

Transições iniciais:

```text
cut
fade
```

---

## 22. B-roll

Preparar arquitetura, mas não implementar automaticamente nesta fase.

Possível abstração futura:

```text
BrollProvider
```

---

## 23. Fact-checking e conteúdo sensível

Não implementar fact-checking web nesta entrega.

Se o CSV contiver:

```text
Verificar afirmação...
```

essa alegação não pode virar automaticamente:

- card factual;
- headline factual;
- intro factual.

Para acusações ou alegações sensíveis, preferir:

```text
"Fulano afirma..."
"Segundo o participante..."
"O trecho discute..."
```

---

## 24. IA no planejamento

Criar abstração:

```python
class EditorialProvider:
    def plan(self, request: EditorialRequest) -> EditorialResult:
        ...
```

Responsabilidade:

- sugerir intro;
- cards;
- frases de destaque;
- subtemas.

Não produzir comandos FFmpeg.

---

## 25. Entrada do provider

Fornecer somente o necessário:

- Tema Principal;
- Título Sugerido;
- Resumo;
- Pergunta Principal;
- Trecho para Validar Primeiro;
- Observações;
- transcrição apenas do trecho;
- metadados da fonte.

Não enviar a transcrição inteira quando o corte já está definido.

---

## 26. Saída estruturada

Usar JSON/schema.

Exemplo:

```json
{
  "intro_text": "...",
  "context_cards": [
    {
      "text": "...",
      "timestamp": 34.0
    }
  ],
  "highlights": [
    {
      "text": "...",
      "start": 82.1,
      "end": 89.7
    }
  ],
  "subtopics": []
}
```

Validar em Python antes de gerar o plano final.

---

## 27. Dry run

```bash
video-editorial editorialize PROJECT --chapter 8 --dry-run
```

Mostrar:

- projeto;
- capítulo;
- corte localizado;
- tema;
- brand;
- provider;
- intro planejada;
- cards;
- destaques;
- CTA;
- arquivo final previsto.

Não renderizar vídeo.

---

## 28. Idempotência e versionamento

Não sobrescrever vídeo final existente.

Preferir:

```text
final/
├── 008_cap08_centrao-governabilidade_v001.mp4
├── 008_cap08_centrao-governabilidade_v002.mp4
```

E:

```text
editorial/.../runs/001/
editorial/.../runs/002/
```

---

## 29. metadata.json

Registrar:

```json
{
  "chapter": 8,
  "source_cut": "...",
  "final_file": "...",
  "brand": "bussola-politica",
  "provider": "...",
  "intro": true,
  "lower_thirds": true,
  "context_cards": 3,
  "highlights": 2,
  "cta": true,
  "status": "rendered"
}
```

---

## 30. Logs e estado

Registrar:

- project;
- chapter;
- run;
- planner;
- provider;
- renderer;
- duração;
- resultado;
- erros.

Preparar status por capítulo:

```text
cut
editorial_planned
editorial_rendered
thumbnail_generated
ready_to_publish
```

---

## 31. Pipeline atualizado

```text
init
↓
download
↓
audio
↓
transcribe
↓
analyze
↓
revisão humana
↓
cut --dry-run
↓
cut
↓
editorialize --dry-run
↓
editorialize
↓
thumbnail
↓
revisão final
↓
publicação
```

---

## 32. Fase 1

Implementar inicialmente:

1. `EditorialPlanner`;
2. `editorial_plan.json`;
3. intro textual;
4. source attribution;
5. lower third simples;
6. cards de contexto/subtema;
7. CTA final;
8. FFmpeg Renderer;
9. dry-run;
10. testes.

---

## 33. Fase 2 futura

Não implementar ainda:

- TTS;
- legendas avançadas;
- frases animadas;
- B-roll;
- imagens externas;
- gráficos;
- mapas;
- fact-checking;
- preview web.

---

## 34. Requisito crítico de timestamps

Os timestamps do `03 Analise.csv` são relativos ao vídeo original.

Após o corte, a timeline editorial deve ser relativa ao início do corte.

Exemplo:

```text
Vídeo original:
29:07 → 37:22

Card relacionado a:
31:07 no original

Timestamp no corte:
02:00
```

Essa conversão deve ser determinística em Python, nunca delegada à IA.

---

## 35. Requisito sobre monetização

A aplicação não deve afirmar:

```text
"vídeo monetizável"
"garantia de monetização"
```

O objetivo da feature é adicionar:

```text
contexto
valor editorial
organização
identidade própria
```

---

## 36. Preparação para SaaS

A lógica deve permanecer desacoplada da CLI.

Evitar dependência de:

- `cwd`;
- prompts interativos na regra de negócio;
- paths absolutos hardcoded;
- macOS específico.

---

## 37. Critérios de aceite

A Fase 1 estará concluída quando for possível:

1. localizar um corte por capítulo;
2. carregar os dados editoriais;
3. gerar `editorial_plan.json`;
4. validar o plano;
5. gerar intro textual;
6. identificar a fonte;
7. criar lower thirds;
8. criar cards;
9. adicionar CTA;
10. renderizar vídeo final;
11. preservar o corte bruto;
12. executar dry-run;
13. versionar outputs;
14. registrar metadata/logs;
15. repetir em outro projeto sem colisão;
16. manter branding configurável;
17. passar testes automatizados.

---

## 38. Testes

Cobrir:

### Planner
- capítulo existente;
- capítulo inexistente;
- dados ausentes;
- conteúdo sensível;
- observações de fact-check.

### Timeline
- eventos sobrepostos;
- evento fora da duração;
- intro;
- CTA;
- timestamps relativos.

### Renderer
- comando FFmpeg;
- paths seguros;
- arquivo existente;
- dry-run.

### Branding
- marca existente;
- marca ausente;
- assets ausentes.

### Provider
Usar mocks. Não chamar APIs reais em testes unitários.

---

## 39. Antes de implementar

NÃO escreva código imediatamente.

Primeiro apresente:

1. estado atual relevante;
2. arquivos reutilizados;
3. arquivos criados;
4. arquivos modificados;
5. arquitetura proposta;
6. estrutura do `editorial_plan.json`;
7. estratégia do planner;
8. estratégia do provider;
9. estratégia da timeline;
10. estratégia de renderização FFmpeg;
11. estratégia de branding;
12. organização dos outputs;
13. versionamento;
14. dry-run;
15. testes;
16. dependências adicionais;
17. impacto no pipeline atual;
18. dúvidas ou decisões pendentes.

Aguarde aprovação antes de implementar.

---

## 40. Primeira decisão de implementação

Priorizar uma versão simples e confiável:

```text
corte bruto
→ intro
→ corte com identidade/contexto
→ CTA
→ vídeo final
```

Não adicionar B-roll, animações complexas ou múltiplos providers antes que esse fluxo esteja funcionando ponta a ponta.
