Sim. Eu acrescentaria isso como um módulo separado do pipeline, porque thumbnail tem uma natureza diferente do corte: o vídeo pode ser gerado automaticamente, mas a capa envolve composição, texto, escolha de personagens e validação editorial.

O fluxo passaria a ser:

03 Analise.csv
      ↓
cortes/*.mp4
      ↓
extração de frames
      ↓
contexto editorial do capítulo
      ↓
geração da thumbnail
      ↓
thumbs/
      ↓
validação humana
      ↓
publicação

O ponto que considero mais importante é não acoplar a aplicação a um único gerador de imagens agora. O módulo deve criar a lógica de seleção de frames, composição do briefing e armazenamento; o provider de geração de imagem deve ser substituível depois.

Você pode entregar o prompt abaixo ao Claude no VS Code quando chegar nessa etapa.

Prompt — Adicionar geração de thumbnails ao Video Editorial

Contexto

Leia integralmente o PRD.md e analise a implementação atual do projeto antes de modificar qualquer arquivo.

O projeto está localizado em:

/Users/vaniojr/Dev/astute4ai/video-editorial

O Video Editorial é atualmente uma aplicação local-first/CLI que organiza:

URL
→ projeto
→ download do vídeo
→ áudio
→ transcrição
→ análise editorial
→ capítulos
→ cortes

Quero adicionar uma nova etapa:

cortes
→ geração de thumbnails
→ validação humana
→ publicação

Não implemente funcionalidades de publicação em redes sociais nesta entrega.

⸻

1. Objetivo

Adicionar ao projeto um módulo responsável por gerar thumbnails editoriais para cada corte aprovado.

A thumbnail deverá utilizar como contexto:

* vídeo original;
* intervalo do corte;
* frames reais extraídos do vídeo;
* informações do capítulo no 03 Analise.csv;
* título sugerido;
* tema principal;
* resumo;
* pergunta principal;
* participantes conhecidos;
* identidade visual configurada para o projeto/canal.

A geração deve produzir thumbnails consistentes entre diferentes vídeos e diferentes canais.

⸻

2. Princípio fundamental

A thumbnail NÃO deve ser produzida apenas a partir de um prompt textual genérico.

O processo deve partir de imagens reais do vídeo.

Fluxo desejado:

03 Analise.csv
      +
video-original.mp4
      ↓
identificar capítulo
      ↓
extrair frames reais
      ↓
selecionar candidatos
      ↓
gerar briefing editorial
      ↓
ImageProvider
      ↓
thumbnail 16:9
      ↓
thumbs/

A aparência das pessoas deve preservar sua identidade visual real.

Evitar gerar do zero rostos de participantes quando frames reais estiverem disponíveis.

⸻

3. Arquitetura

Não acoplar a regra de negócio a um serviço específico de geração de imagens.

Criar abstração semelhante a:

class ThumbnailProvider:
    def generate(self, request: ThumbnailRequest) -> ThumbnailResult:
        ...

Possíveis implementações futuras:

OpenAIImageProvider
OtherImageProvider
LocalCompositionProvider
ManualProvider

A primeira implementação poderá utilizar apenas UM provider funcional.

Porém a arquitetura deve permitir troca sem alterar a lógica principal do pipeline.

⸻

4. Nova estrutura sugerida

Avalie a estrutura atual antes de decidir os nomes finais.

Conceitualmente:

app/
├── thumbnail/
│   ├── __init__.py
│   ├── models.py
│   ├── frames.py
│   ├── briefing.py
│   ├── provider.py
│   ├── service.py
│   └── storage.py

Não criar essa estrutura mecanicamente se a arquitetura atual indicar uma organização melhor.

⸻

5. Organização dentro de cada projeto

Adicionar:

thumbs/

Estrutura desejada:

thumbs/
├── 008_cap08_centrao-governabilidade/
│   ├── frames/
│   │   ├── frame-01.jpg
│   │   ├── frame-02.jpg
│   │   ├── frame-03.jpg
│   │   └── ...
│   │
│   ├── briefing.md
│   ├── metadata.json
│   ├── thumbnail-01.png
│   ├── thumbnail-02.png
│   └── selected.png
│
└── 014_cap14_debates-presidenciais/
    └── ...

selected.png representa a versão aprovada.

Não sobrescrever versões anteriores automaticamente.

⸻

6. CLI

Adicionar comando conceitual:

video-editorial thumbnail PROJECT --chapter 8

Também prever:

video-editorial thumbnail PROJECT --priority A

e:

video-editorial thumbnail PROJECT --all

Adicionar:

--dry-run

No dry-run:

* localizar capítulo;
* validar informações;
* identificar timestamps;
* informar quais frames seriam extraídos;
* gerar briefing;
* NÃO chamar provider de imagem;
* NÃO gerar thumbnail final.

Exemplo:

Projeto:
2026-08-12_podcast-3-irmaos_7xgE4ZHNWRU
Capítulo:
08
Intervalo:
00:29:07 → 00:37:22
Tema:
Governabilidade — Base pequena e Centrão
Frames candidatos:
8
Thumbnail:
1280x720
16:9
Provider:
configured-provider
DRY RUN
Nenhuma imagem final será gerada.

⸻

7. Extração de frames

Usar FFmpeg a partir do vídeo original.

Não depender do arquivo do corte se o vídeo original estiver disponível.

Para cada capítulo, extrair inicialmente entre:

6 e 12 frames

distribuídos ao longo do trecho.

Evitar:

* frames escuros;
* olhos fechados;
* transições;
* motion blur;
* telas vazias;
* logos ocupando a maior parte da tela.

A implementação inicial pode utilizar regras simples.

Não é necessário implementar visão computacional sofisticada nesta entrega.

⸻

8. Estratégia de frames

Não selecionar apenas frames em intervalos matematicamente iguais.

Sempre incluir candidatos próximos de:

início do corte
25%
50%
75%
final

E, quando possível, extrair frames adicionais em regiões de fala.

Posteriormente poderá existir seleção baseada em:

* expressão facial;
* gesticulação;
* pessoa falando;
* qualidade visual;
* presença de múltiplos participantes.

Isso NÃO precisa ser sofisticado no MVP.

⸻

9. Informações editoriais

O módulo deve localizar a linha correspondente no 03 Analise.csv.

Utilizar, quando disponíveis:

Ordem Publicacao
Prioridade
Capitulo
Bloco Editorial
Tema Principal
Titulo Sugerido
Palavra-chave Principal
Trecho para Validar Primeiro
Resumo
Pergunta Principal
Grau de Confianca
Observacoes

Não depender da posição das colunas.

⸻

10. Briefing da thumbnail

Antes de chamar qualquer provider de imagem, gerar:

briefing.md

O briefing deve separar claramente:

FATOS DO CORTE
SUGESTÃO EDITORIAL
ELEMENTOS VISUAIS
TEXTO DA THUMBNAIL
RESTRIÇÕES

Exemplo:

# Thumbnail Briefing
## Capítulo
08
## Tema
Governabilidade com base pequena e relação com o Centrão.
## Participantes
Renan Santos
Kim Kataguiri
Renato Battista
## Mensagem principal
Renan afirma que precisará compor politicamente com partidos do Centrão,
mas diz que não pretende entregar o controle do governo às principais
lideranças desses partidos.
## Texto principal sugerido
NÃO VOU SER USADO
PELO CENTRÃO!
## Texto secundário opcional
Como governar com uma base pequena?
## Direção visual
- Renan em maior destaque.
- Kim como participante secundário.
- Fundo relacionado ao podcast.
- Contraste alto.
- Preto, amarelo e branco.
- Vermelho somente para tensão/destaque.
- Logo da marca pequeno.
## Restrições
- Não inventar participantes.
- Não criar falas que não existam no conteúdo.
- Não atribuir uma opinião da IA ao canal.
- Não apresentar alegações não verificadas como fatos.

⸻

11. Identidade visual

A identidade visual NÃO deve ficar hardcoded como Bússola Política.

Criar configuração por marca/canal.

Exemplo conceitual:

brands/
└── bussola-politica/
    ├── brand.toml
    ├── logo.png
    └── README.md

Possível configuração:

name = "Bússola Política"
primary = "#F5C400"
background = "#090909"
text = "#FFFFFF"
accent = "#C92020"
thumbnail_width = 1280
thumbnail_height = 720
style = "political-editorial"

A implementação deve permitir no futuro:

Bússola Política
Canal de tecnologia
Canal financeiro
Canal esportivo
etc.

sem alterar código.

⸻

12. Linguagem visual inicial da Bússola Política

Como referência editorial inicial, utilizar o padrão já adotado durante os testes manuais:

preto
amarelo
branco
vermelho para tensão
alto contraste
rostos grandes
texto curto
composição editorial
logo discreto

Estilo desejado:

editorial político
podcast/news
alto impacto visual
cinematográfico
legível em telas pequenas

Não transformar a thumbnail em um infográfico cheio de texto.

⸻

13. Hierarquia visual

Prioridade:

1. rosto/personagem
2. mensagem principal
3. conflito ou tema
4. identidade visual
5. elementos secundários

Evitar:

muitos ícones
muitas frases
textos pequenos
parágrafos
mais de 2 mensagens concorrentes

⸻

14. Texto da thumbnail

O texto não precisa ser idêntico ao título do YouTube.

Exemplo:

Título:

Renan Santos: “Não vou ser usado pelo Centrão” |
Como governar com uma base pequena?

Thumbnail:

NÃO VOU SER USADO
PELO CENTRÃO!

A thumbnail deve complementar o título.

⸻

15. Geração de sugestões de texto

Criar função separada para produzir de 1 a 3 opções de headline.

Exemplo:

NÃO VOU SER USADO PELO CENTRÃO!
CENTRÃO: QUEM USA QUEM?
COMO GOVERNAR SEM SE ENTREGAR?

A primeira opção pode ser utilizada automaticamente no MVP.

Salvar todas no metadata.json.

⸻

16. Participantes

Não tentar inferir silenciosamente nomes de pessoas apenas pelas imagens.

A fonte preferencial deve ser:

01 Fonte.md
+
dados editoriais
+
metadados conhecidos

Se participantes não estiverem definidos:

participants_unknown = true

Nesse caso, evitar colocar nomes nas artes automaticamente.

⸻

17. Alegações sensíveis

Thumbnails políticas podem conter afirmações delicadas.

Nunca converter automaticamente observações do CSV em afirmações factuais.

Exemplo:

CSV:

Verificar afirmação de que...

NÃO gerar:

FULANO COMETEU X

Preferir:

FULANO RESPONDE SOBRE X

ou utilizar frase efetivamente pronunciada no corte.

⸻

18. Quotes

Quando usar uma fala entre aspas, ela deve ser derivada de:

transcrição
ou
Trecho para Validar Primeiro

Não inventar citações.

Registrar no metadata:

{
  "headline_type": "quote",
  "quote_source": "transcript"
}

⸻

19. Tamanho da imagem

Configuração padrão inicial:

1280x720
16:9
PNG

Esses valores devem ser configuráveis.

Não espalhar dimensões fixas pelo código.

⸻

20. Safe zones

Manter:

rostos
texto principal
logo

afastados das bordas.

Evitar colocar elementos essenciais nos últimos:

5% de cada lateral

da imagem.

⸻

21. Resultado

Após geração:

thumbnail-01.png

Se forem produzidas múltiplas alternativas:

thumbnail-01.png
thumbnail-02.png
thumbnail-03.png

Não escolher silenciosamente uma versão como final.

⸻

22. Aprovação humana

Adicionar comando conceitual:

video-editorial thumbnail-select PROJECT \
  --chapter 8 \
  --version 2

Resultado:

selected.png

Pode ser:

* cópia;
* symlink;
* registro em metadata.

Escolha a solução mais portátil.

A aprovação humana deve permanecer explícita.

⸻

23. metadata.json

Exemplo:

{
  "chapter": 8,
  "order": 8,
  "cut_file": "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4",
  "headline": "NÃO VOU SER USADO PELO CENTRÃO!",
  "headline_options": [
    "NÃO VOU SER USADO PELO CENTRÃO!",
    "CENTRÃO: QUEM USA QUEM?",
    "COMO GOVERNAR SEM SE ENTREGAR?"
  ],
  "participants": [
    "Renan Santos",
    "Kim Kataguiri",
    "Renato Battista"
  ],
  "frames": [
    "frames/frame-01.jpg",
    "frames/frame-02.jpg"
  ],
  "provider": "provider-name",
  "status": "generated",
  "selected": null
}

⸻

24. Idempotência

Se a thumbnail já existir:

Thumbnail já gerada para capítulo 08.

Não gerar novamente sem:

--new-version

Exemplo:

video-editorial thumbnail PROJECT \
  --chapter 8 \
  --new-version

⸻

25. Custos de API

Se o provider utilizar uma API paga:

Antes da chamada real, mostrar:

1 thumbnail será gerada.
Provider:
...
Imagens:
1
Deseja continuar? [s/N]

Adicionar futuramente:

--yes

Não realizar chamadas pagas durante --dry-run.

⸻

26. Credenciais

Credenciais devem vir de:

.env
variáveis de ambiente
secret manager futuro

Nunca:

project.json
01 Fonte.md
CSV
Git
logs

Adicionar .env ao .gitignore.

⸻

27. Provider sem credencial

Caso não exista configuração do gerador:

NÃO falhar o pipeline inteiro.

Gerar:

frames/
briefing.md
metadata.json

e informar:

Briefing criado.
Nenhum provider de imagem está configurado.

Isso permite geração manual posterior.

⸻

28. Modo manual

Adicionar possibilidade conceitual:

video-editorial thumbnail PROJECT \
  --chapter 8 \
  --provider manual

O modo manual gera apenas:

frames
briefing
metadata

Isso é útil inclusive durante o desenvolvimento.

⸻

29. Estado

Adicionar estados possíveis:

not_started
frames_ready
briefing_ready
generated
selected

Não marcar:

selected

sem ação humana.

⸻

30. Testes

Criar testes para:

Seleção do capítulo

chapter
order
priority

Geração de briefing

Garantir que:

* não invente participante;
* preserve informações do CSV;
* não transforme observação em fato.

Paths

Garantir:

projeto A
não sobrescreve
projeto B

Versionamento

thumbnail-01
thumbnail-02

Dry-run

Garantir que provider não seja chamado.

Provider mock

Utilizar mock para testes.

Não realizar chamadas reais de API nos testes automáticos.

⸻

31. Logs

Registrar:

projeto
capítulo
frames
provider
versão
resultado
horário
erro

Não registrar secrets.

⸻

32. Fora do escopo desta entrega

NÃO implementar:

* upload da thumbnail para YouTube;
* publicação do vídeo;
* Instagram;
* Facebook;
* TikTok;
* geração 1:1;
* geração 9:16;
* Shorts;
* A/B testing automático;
* métricas de CTR;
* escolha automática baseada em performance;
* remoção automática de fundos sofisticada;
* treinamento de modelo;
* reconhecimento facial customizado.

Esses itens podem ser adicionados depois.

⸻

33. Preparação para evolução futura

A arquitetura deve permitir futuramente:

Thumbnail 16:9 → YouTube/Facebook
Thumbnail 1:1  → Instagram
Thumbnail 9:16 → Reels/TikTok/Shorts

Porém implementar somente:

16:9

nesta entrega.

⸻

34. Possível evolução futura com IA

O fluxo poderá evoluir para:

Transcrição
    ↓
IA identifica frase forte
    ↓
IA identifica personagens
    ↓
frames candidatos
    ↓
IA escolhe composição
    ↓
gera 3 thumbnails
    ↓
humano escolhe
    ↓
publicação
    ↓
CTR
    ↓
feedback para próximas thumbnails

Não implementar esse ciclo agora.

⸻

35. Integração com pipeline atual

O comando:

video-editorial thumbnail

deve utilizar projetos já existentes.

NÃO criar um segundo conceito de projeto.

Usar:

project.json
01 Fonte.md
03 Analise.csv
original/
cortes/

como fontes já existentes.

⸻

36. Critérios de sucesso

Esta entrega estará concluída quando for possível:

1. selecionar um projeto existente;
2. selecionar um capítulo;
3. encontrar sua linha no CSV;
4. validar timestamps;
5. extrair frames reais;
6. gerar briefing editorial;
7. montar request de thumbnail;
8. chamar um provider;
9. obter PNG 16:9;
10. armazenar a imagem corretamente;
11. manter versões;
12. aprovar manualmente uma versão;
13. repetir o processo em outro projeto sem sobrescrever arquivos.

⸻

37. Estratégia de implementação

NÃO implemente tudo imediatamente.

Primeiro:

1. analise o PRD;
2. analise a arquitetura atual;
3. identifique quais módulos serão alterados;
4. proponha a integração;
5. apresente quais novas dependências seriam necessárias;
6. explique qual provider pretende usar inicialmente;
7. explique como serão extraídos os frames;
8. explique como evitará acoplamento ao provider;
9. explique como será feito o versionamento;
10. aguarde aprovação.

⸻

38. Primeira resposta esperada

Antes de escrever código, responda com:

1. Estado atual relevante do projeto
2. Arquivos que serão criados
3. Arquivos que serão modificados
4. Fluxo proposto
5. Dependências adicionais
6. Estratégia de frames
7. Estratégia de briefing
8. Estratégia do provider
9. Armazenamento e versionamento
10. Testes planejados
11. Dúvidas ou decisões pendentes

Não implemente até eu aprovar o plano.

Um detalhe que eu considero importante para a implementação: eu não tentaria reproduzir imediatamente 100% do que fizemos aqui com IA generativa. Primeiro faria o módulo entregar muito bem frames + briefing + headline + metadata. Depois conectaria o provider de imagem.

Isso nos permite testar toda a inteligência editorial sem gastar chamadas de geração nem misturar problemas de IA com problemas de organização do pipeline. Quando essa base estiver estável, a geração automática da imagem entra como uma camada relativamente isolada.