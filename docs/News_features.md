# Planejamento Consolidado — Editorialização + Thumbnails

## Contexto

Leia integralmente antes de qualquer implementação:

- `PRD.md`
- `docs/PIPELINE.md`
- implementação atual do projeto
- testes existentes
- `Feature_Editorializacao_Automatica.md`
- `Feature_thumbnail.md`

O projeto está localizado em:

`/Users/vaniojr/Dev/astute4ai/video-editorial`

As etapas existentes do pipeline já foram implementadas e testadas até a geração dos cortes.

Existem agora duas novas features planejadas:

1. **Editorialização automática dos cortes**
2. **Geração de thumbnails**

Essas duas features foram especificadas separadamente, porém possuem conceitos, estruturas e dependências em comum.

Por isso, **NÃO implemente nenhuma das duas features ainda**.

Quero primeiro uma análise arquitetural conjunta e um roadmap consolidado das próximas entregas.

---

# 1. Pipeline-alvo

Considere como visão atual do pipeline:

`init → download → audio → transcribe → analyze → revisão humana → cut → editorialize → thumbnail → revisão final → publicação`

A etapa de publicação ainda é futura e está fora do escopo atual.

O objetivo imediato é evoluir de:

`cut`

para:

`cut → editorialize → thumbnail`

sem criar duplicações arquiteturais ou acoplamentos que dificultem a futura evolução para SaaS.

---

# 2. Objetivo desta atividade

Analise conjuntamente:

- `Feature_Editorializacao_Automatica.md`
- `Feature_thumbnail.md`

e compare essas especificações com a implementação real existente.

Não assuma que cada documento de feature precisa virar uma única entrega.

Quero que as features sejam quebradas em **entregas menores, incrementais, testáveis e que produzam valor individualmente**.

O resultado desta atividade deve ser um **roadmap técnico**, e não código.

---

# 3. Análise de dependências

Identifique claramente:

1. dependências entre Editorialização e Thumbnail;
2. componentes que podem ser compartilhados;
3. componentes que devem permanecer separados;
4. alterações necessárias na arquitetura atual;
5. riscos de implementar Thumbnail primeiro;
6. riscos de implementar Editorialização primeiro;
7. qual ordem de implementação é tecnicamente mais adequada;
8. quais decisões precisam ser tomadas antes da implementação.

Ao final dessa análise, recomende explicitamente qual feature ou subfeature deve ser implementada primeiro.

---

# 4. Evitar duplicação arquitetural

Dê atenção especial aos conceitos presentes nas duas features.

Analise se devem existir componentes compartilhados para:

- branding;
- configuração de marca/canal;
- assets da marca;
- leitura de `03 Analise.csv`;
- localização de capítulos;
- modelos de capítulo;
- identificação de participantes;
- metadata;
- estados por capítulo;
- versionamento;
- organização dos outputs;
- providers de IA;
- configuração de providers;
- secrets;
- logs;
- dry-run;
- confirmação de custos;
- paths do projeto;
- FFmpeg;
- validação de timestamps.

Não quero terminar, por exemplo, com duas implementações independentes equivalentes a:

`editorial/branding.py`

e:

`thumbnail/branding.py`

caso ambas representem o mesmo conceito.

Se fizer sentido, proponha abstrações compartilhadas.

Exemplo meramente conceitual:

`app/brands/`

`app/chapters/`

`app/providers/`

`app/media/`

Porém NÃO crie essas estruturas apenas porque foram sugeridas aqui.

Primeiro avalie a arquitetura existente e proponha a solução mais coerente com o projeto atual.

---

# 5. Branding compartilhado

Editorialização e Thumbnail utilizarão identidade visual da mesma marca.

Analise se deve existir uma configuração única semelhante a:

`brands/bussola-politica/`

contendo conceitualmente:

- nome;
- logo;
- cores;
- fontes;
- estilo visual;
- assets;
- configurações de vídeo;
- configurações de thumbnail.

O objetivo é evitar que cada módulo tenha sua própria definição da Bússola Política.

Também deve ser possível futuramente adicionar outras marcas/canais sem alteração da regra de negócio.

---

# 6. Capítulo como entidade central

Analise se, considerando a evolução atual, o conceito de **capítulo/corte editorial** deve passar a possuir uma representação compartilhada.

Hoje diferentes etapas utilizam informações como:

- capítulo;
- ordem de publicação;
- prioridade;
- timestamps;
- título;
- tema;
- resumo;
- observações;
- arquivo do corte;
- estado da editorialização;
- thumbnail;
- versão selecionada.

Avalie se faz sentido introduzir uma abstração/modelo compartilhado para evitar que cada feature faça parsing independente do `03 Analise.csv`.

Não alterar o CSV como contrato do pipeline sem necessidade.

---

# 7. Estado por capítulo

O projeto agora pode possuir diferentes capítulos em estados diferentes.

Exemplo:

- capítulo 08: vídeo final pronto;
- capítulo 14: apenas cortado;
- capítulo 17: thumbnail aguardando aprovação.

Analise como representar isso.

Estados conceituais possíveis:

`analyzed`

`cut`

`editorial_planned`

`editorial_rendered`

`thumbnail_frames_ready`

`thumbnail_generated`

`thumbnail_selected`

`ready_to_publish`

Não implemente necessariamente esses nomes.

Proponha o modelo mais adequado.

Evitar depender exclusivamente de um status global do projeto quando o estado real pertence ao capítulo.

---

# 8. Relação entre vídeo editorializado e thumbnail

A feature de thumbnail originalmente considera frames extraídos do vídeo original.

A feature de editorialização passa a gerar um novo:

`video-final.mp4`

Analise cuidadosamente qual deve ser a fonte de frames para thumbnail:

- vídeo original;
- corte bruto;
- vídeo editorializado;
- combinação dessas fontes.

Considere que os melhores frames de rosto podem estar no vídeo original/corte, enquanto o vídeo editorializado pode conter intro, cards e outros elementos gráficos.

Proponha uma estratégia clara e justifique.

---

# 9. Providers de IA

As features podem utilizar diferentes tipos de provider:

- análise textual;
- planejamento editorial;
- geração de thumbnail;
- futuramente TTS;
- futuramente B-roll.

Não quero uma abstração genérica demais como um único `AIProvider` responsável por tudo.

Também não quero duplicação desnecessária de:

- configuração;
- autenticação;
- retry;
- logging;
- usage;
- secrets.

Analise qual deve ser a fronteira entre infraestrutura compartilhada e interfaces específicas.

Exemplos conceituais:

`AnalysisProvider`

`EditorialProvider`

`ThumbnailProvider`

`VoiceProvider`

Podem compartilhar infraestrutura, mas devem manter contratos específicos.

---

# 10. Editorialização — decomposição

Não trate `Feature_Editorializacao_Automatica.md` necessariamente como uma única entrega.

Avalie a possibilidade de dividir em fases como:

### Base

- modelos;
- configuração de branding;
- estrutura de outputs;
- timeline;
- estado por capítulo.

### Planejamento editorial

- `EditorialPlanner`;
- provider;
- `editorial_plan.json`;
- validação;
- dry-run.

### Renderização

- intro;
- source attribution;
- lower thirds;
- cards;
- CTA;
- FFmpeg Renderer.

### Recursos avançados futuros

- TTS;
- legendas avançadas;
- B-roll;
- gráficos;
- mapas;
- fact-checking.

Determine a divisão adequada após analisar o código real.

---

# 11. Thumbnail — decomposição

Também não trate `Feature_thumbnail.md` necessariamente como uma única entrega.

Avalie uma divisão como:

### Base

- estrutura de diretórios;
- integração com capítulos;
- branding compartilhado;
- metadata.

### Frames

- extração via FFmpeg;
- seleção de candidatos;
- armazenamento;
- dry-run.

### Briefing

- contexto editorial;
- headlines;
- participantes;
- `briefing.md`;
- metadata.

### Provider

- `ThumbnailProvider`;
- geração 16:9;
- versionamento;
- custos;
- fallback manual.

### Aprovação

- seleção humana;
- `selected.png`;
- estados.

Determine a divisão final depois de analisar a implementação atual.

---

# 12. Reutilização do FFmpeg

O projeto já utiliza FFmpeg para geração de cortes.

Analise quais componentes existentes podem ser reutilizados para:

- extração de frames;
- geração de intro;
- overlays;
- lower thirds;
- cards;
- concatenação;
- CTA;
- renderização final.

Não criar uma segunda infraestrutura FFmpeg independente se a atual puder ser evoluída.

---

# 13. Estrutura de diretórios

Analise como os novos artefatos devem coexistir dentro de cada projeto.

Hoje existem artefatos como:

`01 Fonte.md`

`02 Transcricao.md`

`03 Analise.csv`

`project.json`

`original/`

`audio/`

`cortes/`

As novas features propõem estruturas como:

`editorial/`

`final/`

`thumbs/`

Avalie se essa organização continua adequada.

Apresente uma árvore completa de exemplo para um projeto após todas as etapas:

`download → transcribe → analyze → cut → editorialize → thumbnail`

A árvore deve mostrar claramente:

- arquivos oficiais;
- intermediários;
- versões;
- assets;
- metadata;
- arquivos temporários.

---

# 14. Artefatos oficiais versus intermediários

Defina claramente quais arquivos são contratos oficiais do pipeline e quais são apenas artefatos internos.

Exemplo conceitual:

### Oficiais

`01 Fonte.md`

`02 Transcricao.md`

`03 Analise.csv`

`cortes/*.mp4`

`final/*.mp4`

`thumbs/.../selected.png`

### Intermediários

`editorial_plan.json`

frames candidatos

briefing

assets temporários

logs

previews

Não assumir essa classificação automaticamente.

Analise e proponha a definição correta.

---

# 15. Versionamento

Editorialização e thumbnail podem gerar múltiplas versões.

Proponha uma estratégia única e consistente.

Exemplo:

`v001`

`v002`

`v003`

Avalie:

- onde fica a versão;
- como metadata referencia a versão;
- como identificar versão ativa;
- como evitar sobrescrita;
- como selecionar versão aprovada;
- como manter histórico.

Evitar implementar mecanismos diferentes de versionamento em cada módulo.

---

# 16. Dry-run

O projeto já utiliza o conceito de `--dry-run`.

Quero manter comportamento consistente.

Analise o que cada comando deve fazer em:

`editorialize --dry-run`

e:

`thumbnail --dry-run`

Defina claramente:

- o que é validado;
- quais arquivos podem ser criados;
- se providers podem ser chamados;
- se FFmpeg pode ser executado;
- como custos são evitados.

Como regra geral, `--dry-run` não deve gerar custos externos.

---

# 17. Revisão humana

Mesmo com automação, quero manter pontos explícitos de revisão.

Pipeline conceitual:

`analyze`

→ revisão do `03 Analise.csv`

→ `cut`

→ `editorialize`

→ `thumbnail`

→ seleção da thumbnail

→ revisão final

→ publicação futura.

Identifique quais estados precisam de aprovação humana e quais podem avançar automaticamente.

---

# 18. Preparação para futura orquestração

Não implementar agora:

`video-editorial process URL`

Porém a arquitetura deve permitir futuramente uma orquestração como:

`init → download → audio → transcribe → analyze → pause/review → cut → editorialize → thumbnail → pause/review → publish`

Evitar decisões que obriguem uma grande refatoração para isso.

---

# 19. Preparação para SaaS

O projeto continua local-first/CLI neste momento.

Porém os services devem ser utilizáveis futuramente por:

- API;
- worker;
- frontend;
- fila de processamento.

Evitar regra de negócio dependente diretamente de:

- CLI;
- `cwd`;
- prompts interativos;
- macOS;
- paths absolutos;
- terminal.

A CLI deve funcionar como camada de entrada para services reutilizáveis.

---

# 20. Roadmap esperado

Depois da análise, proponha um roadmap numerado.

Não precisa obrigatoriamente utilizar estes números, mas quero estrutura semelhante a:

## Entrega 8.1 — Fundação compartilhada

### Objetivo

### Por que vem primeiro

### Arquivos criados

### Arquivos modificados

### Dependências

### Critérios de aceite

### Testes

---

## Entrega 8.2 — Planejamento editorial

### Objetivo

### Dependências

### Critérios de aceite

### Testes

---

## Entrega 8.3 — Renderização editorial

...

---

## Entrega 9.1 — Frames e briefing de thumbnail

...

---

## Entrega 9.2 — Provider de thumbnail

...

A numeração e divisão devem ser propostas com base na arquitetura real.

---

# 21. Cada entrega deve ser pequena

Evitar uma entrega equivalente a:

"Implementar toda a editorialização."

ou:

"Implementar todo o thumbnail."

Cada entrega deve:

- possuir objetivo claro;
- ser testável isoladamente;
- produzir valor;
- ter critérios de aceite;
- deixar o projeto funcionando;
- evitar grandes mudanças simultâneas.

---

# 22. Identificar conflitos entre os documentos

Os dois documentos foram escritos separadamente.

Identifique:

- requisitos duplicados;
- conceitos equivalentes com nomes diferentes;
- estruturas redundantes;
- possíveis conflitos;
- decisões que ficaram inconsistentes;
- funcionalidades que deveriam ser compartilhadas.

Para cada conflito, proponha uma decisão consolidada.

Não implemente silenciosamente uma das versões.

---

# 23. Identificar oportunidades de simplificação

Se alguma parte das features estiver complexa demais para o estágio atual, sinalize.

Classifique quando possível:

`necessário agora`

`preparar arquitetura`

`implementar depois`

`fora do escopo`

O objetivo é evitar overengineering.

---

# 24. Resultado esperado desta análise

Sua resposta deve conter, nesta ordem:

## 1. Estado atual relevante do projeto

O que já existe e será reutilizado.

## 2. Comparação das duas features

Responsabilidades de cada uma e pontos de interseção.

## 3. Dependências

O que depende de quê.

## 4. Requisitos compartilhados

O que deve existir uma única vez.

## 5. Conflitos ou duplicações

Problemas encontrados nos documentos.

## 6. Arquitetura consolidada proposta

Incluindo árvore conceitual dos módulos.

## 7. Modelo de dados/estado por capítulo

Como acompanhar o ciclo de vida de cada corte.

## 8. Estrutura de diretórios final

Exemplo completo de um projeto.

## 9. Estratégia de providers

O que é compartilhado e o que permanece específico.

## 10. Estratégia de branding

Como Editorialização e Thumbnail compartilham a mesma identidade.

## 11. Estratégia de versionamento

Vídeos, planos e thumbnails.

## 12. Estratégia de revisão humana

Onde o pipeline pausa.

## 13. Roadmap de entregas

Entregas pequenas e ordenadas.

## 14. Testes por entrega

Unitários, integração e smoke tests.

## 15. Riscos técnicos

Principalmente FFmpeg, providers, estado e organização dos artefatos.

## 16. Itens que devem ficar para depois

Para evitar overengineering.

## 17. Próxima entrega recomendada

Escolha UMA única entrega para ser implementada primeiro e explique por quê.

---

# 25. Regra final

NÃO implemente código nesta atividade.

NÃO modifique arquivos.

NÃO instale dependências.

NÃO faça refatorações.

NÃO inicie Editorialização.

NÃO inicie Thumbnail.

Esta atividade é exclusivamente de:

`análise → consolidação → arquitetura → roadmap`

Ao final, aguarde minha aprovação antes de iniciar a primeira entrega.