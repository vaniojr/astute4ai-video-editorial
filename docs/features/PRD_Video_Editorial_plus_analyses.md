Feature — Automação da Análise Editorial com LLM

1. Contexto

Leia integralmente o PRD.md, o docs/PIPELINE.md caso já exista, o código atual e os testes antes de implementar esta alteração.

O pipeline atual possui uma etapa manual:

01 Fonte.md
+
02 Transcricao.md
↓
análise editorial manual
↓
03 Analise.csv

Segundo a implementação atual, o operador utiliza 01 Fonte.md e 02 Transcricao.md externamente para produzir 03 Analise.csv.

Quero substituir essa etapa por uma análise editorial automatizada através de LLM.

O primeiro provider será a API da Anthropic/Claude.

Entretanto, Claude NÃO deve ficar acoplado à regra de negócio.

A arquitetura deve permitir futuramente utilizar outros providers, como:

Claude
OpenAI
Gemini
modelo local
outro provider

sem reescrever o pipeline editorial.

⸻

2. Objetivo

Adicionar o comando:

video-editorial analyze PROJECT

Fluxo esperado:

01 Fonte.md
      +
02 Transcricao.md
      ↓
AnalysisService
      ↓
AnalysisProvider
      ↓
Claude API
      ↓
resposta estruturada
      ↓
validação
      ↓
03 Analise.csv

O arquivo gerado deve permanecer compatível com a etapa de corte já existente.

⸻

3. Princípio arquitetural

Separar claramente:

regra editorial
provider de IA
prompt
schema de resposta
conversão para CSV

NÃO implementar algo equivalente a:

def analyze():
    client = Anthropic(...)
    ...

misturando todas as responsabilidades.

Preferir conceitualmente:

AnalysisService
    ↓
AnalysisProvider
    ↓
ClaudeAnalysisProvider

Exemplo conceitual:

class AnalysisProvider(Protocol):
    def analyze(
        self,
        request: AnalysisRequest
    ) -> AnalysisResult:
        ...

Implementação inicial:

class ClaudeAnalysisProvider:
    ...

⸻

4. Responsabilidades

AnalysisService

Responsável por:

localizar projeto
ler fonte
ler transcrição
carregar prompt
montar AnalysisRequest
chamar provider
validar resultado
gerar CSV
atualizar estado
registrar execução

AnalysisProvider

Responsável somente por:

enviar conteúdo ao modelo
receber resposta
converter resposta para estrutura conhecida

ClaudeAnalysisProvider

Responsável pelos detalhes específicos da API Anthropic:

cliente
modelo
parâmetros
request
response
erros da API

⸻

5. Arquitetura sugerida

Analise primeiro a estrutura atual.

Conceitualmente:

app/
├── analysis/
│   ├── __init__.py
│   ├── models.py
│   ├── provider.py
│   ├── service.py
│   ├── validator.py
│   ├── csv_writer.py
│   └── providers/
│       ├── __init__.py
│       └── claude.py

Se a arquitetura existente indicar organização melhor, adapte.

Não reorganize módulos não relacionados sem necessidade.

⸻

6. Prompt editorial

O prompt NÃO deve ficar hardcoded dentro do provider.

Criar:

prompts/
└── analysis/
    ├── system.md
    └── editorial.md

ou estrutura equivalente compatível com o projeto.

O prompt deve ser versionável em Git.

Isso permitirá alterar a metodologia editorial sem alterar código Python.

⸻

7. Separação entre prompt e marca

Evitar inserir regras exclusivas da Bússola Política diretamente no código.

Preparar conceitualmente:

brands/
└── bussola-politica/
    └── analysis.md

ou configuração equivalente.

O sistema deve futuramente permitir:

video-editorial analyze PROJECT --brand bussola-politica

Não é obrigatório implementar múltiplas marcas nesta entrega, mas não criar acoplamento que impeça isso.

⸻

8. Entradas da análise

Obrigatórias:

01 Fonte.md
02 Transcricao.md

Opcionalmente:

project.json
configuração editorial
brand context

O provider não deve acessar arquivos diretamente.

O AnalysisService lê os arquivos e monta um objeto:

AnalysisRequest

Exemplo conceitual:

AnalysisRequest(
    source=source_content,
    transcript=transcript_content,
    editorial_instructions=prompt_content,
    metadata=project_metadata,
)

⸻

9. Saída estruturada

NÃO pedir ao modelo para gerar CSV diretamente.

O modelo deve retornar dados estruturados.

Preferência:

JSON estruturado

Depois:

JSON
 ↓
validação Python
 ↓
modelos internos
 ↓
CSV Writer
 ↓
03 Analise.csv

Isso evita problemas com:

vírgulas
quebras de linha
aspas
acentuação
encoding
colunas faltantes
ordem das colunas

⸻

10. Schema de capítulo

Cada capítulo deve possuir, no mínimo:

ordem_publicacao
prioridade
capitulo
bloco_editorial
acao_editorial
timestamp_inicial
timestamp_final
duracao
tema_principal
titulo_sugerido
palavra_chave_principal
trecho_validar_primeiro
resumo
pergunta_principal
independente
precisa_contexto_anterior
grau_confianca
observacoes

O schema interno pode utilizar nomes Python-friendly.

O CSV final deve preservar o cabeçalho definido pelo projeto:

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

⸻

11. Validação obrigatória

Nunca aceitar silenciosamente a resposta do LLM.

Antes de gerar 03 Analise.csv, validar:

schema
tipos
campos obrigatórios
capítulos duplicados
timestamps
ordem temporal
duração
ações editoriais
prioridades
valores booleanos
grau de confiança

Reutilizar o parser/validador de timestamps já existente sempre que possível.

Não criar uma segunda implementação concorrente.

⸻

12. Validação contra o vídeo

Quando a duração real estiver disponível em project.json ou via ffprobe, validar:

timestamp inicial >= 0
timestamp final > timestamp inicial
timestamp final <= duração do vídeo

Também comparar:

timestamp final - timestamp inicial

com:

Duracao

informada pela IA.

Preferencialmente calcular Duracao no código em vez de confiar no cálculo do modelo.

⸻

13. Responsabilidade da IA sobre timestamps

A IA deve identificar:

Timestamp Inicial
Timestamp Final

a partir da transcrição.

Porém a aplicação é responsável por:

normalizar
validar
calcular duração

Não confiar na IA para operações determinísticas que o código pode executar.

⸻

14. Metodologia editorial

O prompt deve orientar o modelo a identificar blocos que:

possuam assunto compreensível
tenham início e fim editorial
tenham potencial para publicação isolada
preservem contexto suficiente
evitem cortes enganosos
evitem retirar falas de contexto

A análise deve distinguir:

Manter
Revisar
Descartar

ou os valores já suportados pelo pipeline atual.

⸻

15. Prioridade

Utilizar inicialmente:

A
B
C

Conceito:

A = alto potencial editorial/publicação
B = bom conteúdo, prioridade secundária
C = conteúdo complementar/baixa prioridade

As definições completas devem ficar no prompt editorial, não no código.

⸻

16. Conteúdo sensível

A análise deve sinalizar, e NÃO tentar verificar autonomamente, afirmações como:

acusações
crimes
corrupção
dados financeiros
alegações sobre terceiros
estatísticas
datas relevantes
afirmações jurídicas
alegações potencialmente difamatórias

Utilizar:

Trecho para Validar Primeiro
Observacoes

para registrar necessidade de fact-checking.

Exemplo:

Verificar afirmação sobre X antes da publicação.

A IA não deve transformar uma alegação feita no vídeo em fato editorial.

⸻

17. Neutralidade da descrição

Distinguir sempre:

"Fulano afirma que..."

de:

"X aconteceu."

quando a transcrição apenas comprova que alguém fez a afirmação.

Essa regra é especialmente importante para conteúdo político.

⸻

18. Transcrição longa

A arquitetura deve considerar que podcasts/lives podem possuir:

1 hora
2 horas
3 horas
ou mais

e ultrapassar limites práticos de contexto ou custo.

NÃO assumir que toda transcrição será enviada em uma única chamada.

⸻

19. Estratégia para transcrições longas

Projetar o AnalysisService para permitir:

transcrição
 ↓
chunks
 ↓
análise parcial
 ↓
resultados intermediários
 ↓
consolidação
 ↓
análise final

Conceitualmente:

MAP
↓
analisar blocos
REDUCE
↓
consolidar capítulos

Evitar dividir no meio de segmentos da transcrição.

Preferir boundaries baseados nos timestamps/segmentos já existentes.

⸻

20. Overlap

Quando houver chunking, utilizar pequena sobreposição entre blocos para evitar perder assuntos que atravessem uma fronteira.

Exemplo conceitual:

Chunk 1
00:00 → 20:30
Chunk 2
20:00 → 40:30

O tamanho deve ser configurável.

Não hardcode números sem necessidade.

⸻

21. Consolidação

Após análises parciais, a etapa de consolidação deve:

remover duplicatas
unir capítulos sobrepostos
corrigir ordem
preservar timestamps
reclassificar prioridade se necessário

Não depender da ordem em que respostas da API retornarem.

⸻

22. Artefatos intermediários

Para auditoria e debugging, considerar:

analysis/
├── raw/
│   ├── chunk-001.json
│   ├── chunk-002.json
│   └── ...
│
├── consolidated.json
└── validation.json

O arquivo oficial continua sendo:

03 Analise.csv

Não obrigar o operador a editar os JSON intermediários.

⸻

23. Organização do projeto

Adicionar ao projeto processado:

analysis/

Exemplo:

projetos/.../
├── 01 Fonte.md
├── 02 Transcricao.md
├── 03 Analise.csv
│
└── analysis/
    ├── raw/
    ├── consolidated.json
    └── validation.json

⸻

24. CLI

Adicionar:

video-editorial analyze PROJECT

Opções previstas:

--provider claude
--model MODEL
--dry-run
--force

Provider padrão deve vir da configuração.

Não exigir --provider claude em toda execução.

⸻

25. Dry Run

Implementar:

video-editorial analyze PROJECT --dry-run

O dry-run deve mostrar:

Projeto
Provider
Modelo
Fonte encontrada
Transcrição encontrada
Tamanho da transcrição
Quantidade estimada de chunks
Prompt utilizado
Arquivo de saída

Não chamar a API.

Exemplo:

Projeto:
2026-08-12_podcast-3-irmaos_7xgE4ZHNWRU
Provider:
claude
Modelo:
<modelo configurado>
Transcrição:
02 Transcricao.md
Caracteres:
187.422
Chunks planejados:
6
Saída:
03 Analise.csv
DRY RUN
Nenhuma chamada de API realizada.

⸻

26. Confirmação antes de custo

Antes de realizar chamadas reais:

Provider: Claude
Modelo: ...
Chunks: 6
A análise utilizará uma API externa e poderá gerar custos.
Continuar? [s/N]

Prever:

--yes

para automação futura.

⸻

27. Credenciais

Utilizar:

ANTHROPIC_API_KEY

via variável de ambiente ou .env.

Nunca armazenar API key em:

project.json
01 Fonte.md
03 Analise.csv
logs
Git

Garantir:

.env

Fornecer:

.env.example

sem segredo real.

Exemplo:

ANTHROPIC_API_KEY=

⸻

28. Configuração

Não hardcode o modelo Claude.

Criar configuração equivalente a:

[analysis]
provider = "claude"
model = "..."
temperature = 0

O nome exato do modelo deve ser configurável.

Isso permite atualização sem alteração de código.

⸻

29. Provider Factory

Preparar resolução conceitual:

provider = get_analysis_provider(config.analysis.provider)

Inicialmente:

claude → ClaudeAnalysisProvider

Futuramente:

openai → OpenAIAnalysisProvider
gemini → GeminiAnalysisProvider
local → LocalAnalysisProvider

Não implementar providers futuros agora.

⸻

30. Dependência Anthropic

Adicionar o SDK oficial da Anthropic às dependências do projeto utilizando o gerenciador já adotado pelo projeto.

Não criar integração HTTP manual se o SDK oficial atender ao requisito.

Consultar a documentação atual do SDK antes de implementar.

⸻

31. Retry

Erros transitórios de API não devem obrigar a recomeçar uma análise longa do zero.

Implementar estratégia limitada de retry para erros apropriados, como:

rate limit
timeout
erro temporário do serviço

Não repetir indefinidamente.

Não fazer retry automático para:

credencial inválida
schema permanentemente inválido
configuração incorreta

⸻

32. Resume

Se uma análise possuir vários chunks e falhar no chunk 5:

chunk 1 OK
chunk 2 OK
chunk 3 OK
chunk 4 OK
chunk 5 ERRO

uma nova execução deve, quando seguro, reutilizar os chunks válidos.

Não pagar novamente por chamadas já concluídas sem necessidade.

Preparar:

video-editorial analyze PROJECT --resume

ou comportamento equivalente claramente documentado.

⸻

33. Idempotência

Se existir:

03 Analise.csv

não sobrescrever automaticamente.

Mostrar:

A análise já existe para este projeto.

Exigir:

--force

ou mecanismo de nova versão.

Preferência por preservar a análise anterior.

⸻

34. Versionamento das análises

Como prompts e modelos podem mudar, considerar armazenar versões:

analysis/
└── runs/
    ├── 001/
    ├── 002/
    └── ...

Cada execução deve registrar:

provider
modelo
prompt version
data
resultado

O 03 Analise.csv pode representar a versão ativa/aprovada.

Não criar complexidade excessiva, mas não perder rastreabilidade.

⸻

35. Prompt version

Todo resultado deve registrar qual versão do prompt produziu a análise.

Exemplo:

analysis_prompt_version = 1

Isso será importante para comparar resultados posteriormente.

⸻

36. Observabilidade de tokens e custo

Quando o provider retornar usage, registrar:

input tokens
output tokens
quantidade de chamadas
modelo

Se for possível calcular custo de forma confiável através de configuração, registrar.

Não hardcode preços da API no código como verdade permanente.

Preço muda.

O sistema pode inicialmente registrar apenas usage.

⸻

37. Logs

Registrar:

timestamp
project
provider
model
run
chunk
duration
status
usage
error type

Nunca registrar:

API key
segredos
credenciais

Evitar registrar a transcrição inteira nos logs.

⸻

38. Status do projeto

O estado:

analyzed

somente deve ser definido após:

resposta recebida
+
schema validado
+
timestamps validados
+
03 Analise.csv escrito com sucesso

Falha parcial não deve marcar projeto como analisado.

⸻

39. Revisão humana permanece

Automatizar a geração de 03 Analise.csv NÃO significa eliminar a validação editorial.

Novo fluxo:

Claude
 ↓
03 Analise.csv
 ↓
REVISÃO HUMANA
 ↓
cut --dry-run
 ↓
cut

O operador deve continuar podendo editar manualmente o CSV antes dos cortes.

O comando cut deve sempre trabalhar com o CSV existente, independentemente de ele ter sido criado por IA ou manualmente.

⸻

40. Não acoplar CUT ao Claude

Esta regra é obrigatória.

cut NÃO deve:

chamar Claude
chamar AnalysisService
exigir Anthropic

O contrato entre as etapas continua sendo:

03 Analise.csv

Isso permite:

análise Claude
OU
análise OpenAI
OU
análise manual
       ↓
03 Analise.csv
       ↓
cut

⸻

41. Falha da API

Se Claude estiver indisponível:

download
audio
transcribe

continuam funcionando.

O usuário também deve continuar podendo criar:

03 Analise.csv

manualmente.

A integração com LLM é uma capacidade adicional, não uma dependência estrutural de todo o produto.

⸻

42. Testes

Criar testes para:

AnalysisService

* arquivos ausentes;
* projeto válido;
* análise já existente;
* force;
* status.

Provider

Utilizar mock.

NUNCA chamar API Claude real nos testes unitários.

Schema

Testar:

campo ausente
tipo inválido
capítulo duplicado
timestamp inválido
timestamp fora do vídeo

Chunking

Testar:

transcrição curta
transcrição longa
overlap
fronteiras

Consolidation

Testar:

capítulos duplicados
capítulos sobrepostos
ordem

CSV

Testar:

UTF-8
acentuação
aspas
vírgulas
quebras de linha
ordem do cabeçalho

⸻

43. Segurança de conteúdo

Não executar qualquer conteúdo produzido pela IA como:

shell
Python
path
comando FFmpeg

sem validação.

A saída da IA é dado, nunca código confiável.

⸻

44. Documentação

Atualizar:

README.md
docs/PIPELINE.md
.env.example

O pipeline documentado passa de:

transcribe
→ análise manual
→ cut

para:

transcribe
→ analyze
→ revisão humana
→ cut --dry-run
→ cut

Documentar também o fallback:

transcribe
→ análise manual
→ 03 Analise.csv
→ cut

⸻

45. Fluxo final esperado

video-editorial init URL
        ↓
video-editorial download PROJECT
        ↓
video-editorial audio PROJECT
        ↓
video-editorial transcribe PROJECT
        ↓
video-editorial analyze PROJECT --dry-run
        ↓
video-editorial analyze PROJECT
        ↓
03 Analise.csv
        ↓
REVISÃO HUMANA
        ↓
video-editorial cut PROJECT --dry-run
        ↓
video-editorial cut PROJECT

⸻

46. Fora do escopo

NÃO implementar nesta entrega:

thumbnails
upload YouTube
Facebook
Instagram
TikTok
publicação
agendamento
analytics
fact-checking automático na web
aprovação automática
process URL ponta a ponta
frontend
SaaS
outros providers reais

Somente Claude deve ser implementado como provider real inicialmente.

⸻

47. Critérios de aceite

A feature estará concluída quando:

1. analyze aceitar um projeto válido;
2. localizar 01 Fonte.md;
3. localizar 02 Transcricao.md;
4. carregar o prompt editorial;
5. dividir transcrições longas quando necessário;
6. chamar Claude através de provider abstrato;
7. obter resposta estruturada;
8. validar o schema;
9. validar timestamps;
10. calcular durações deterministicamente;
11. consolidar resultados;
12. gerar 03 Analise.csv UTF-8;
13. preservar acentuação;
14. registrar provider/model/prompt version;
15. não sobrescrever análise existente silenciosamente;
16. permitir retomada após falha quando aplicável;
17. permitir edição manual do CSV;
18. manter cut completamente independente do provider;
19. passar testes automatizados;
20. atualizar documentação.

⸻

48. Antes de implementar

NÃO escreva código imediatamente.

Primeiro apresente:

1. Estado atual relevante do projeto
2. Arquivos existentes que serão reutilizados
3. Arquivos que serão criados
4. Arquivos que serão modificados
5. Arquitetura AnalysisService / AnalysisProvider
6. Formato de AnalysisRequest e AnalysisResult
7. Estratégia de structured output
8. Estratégia para transcrições longas
9. Estratégia de consolidação
10. Estratégia de validação
11. Estratégia de retry/resume
12. Configuração e secrets
13. Alterações na CLI
14. Testes
15. Impacto no pipeline atual
16. Decisões ou dúvidas pendentes

Aguarde aprovação do plano antes de implementar.