# Metodologia de planejamento editorial

## Intro (`intro_text`)

Um texto curto (o suficiente para 8 a 15 segundos de leitura em voz alta) que dá contexto ao espectador antes do corte começar. Exemplo de tom:

"Neste trecho, Renan Santos explica como pretende negociar com o Centrão caso seja eleito, sem entregar o controle do governo."

A intro nunca inventa fatos nem converte uma alegação em fato consumado. Se o corte já é autoexplicativo, prefira `intro_text` vazio a forçar uma intro artificial.

## Cards de contexto (`context_cards`, `kind: "context"`)

0 a 4 cards curtos que ajudam o espectador a entender o cenário do corte — tema do debate, quem são os participantes, de onde vem o conteúdo. Exemplos:

```
CONTEXTO
O debate trata da formação de maioria no Congresso.
```

```
FONTE
Podcast 3 Irmãos #1033
```

Use `position_fraction` para sugerir em que momento do corte o card deveria aparecer (0.0 = logo no início, 1.0 = perto do final).

## Cards de subtema (`context_cards`, `kind: "subtopic"`)

Só para cortes longos com mais de um assunto: marque transições de subtema, ex.:

```
1. Como formar maioria?
2. Relação com o Centrão
```

Não recorte o vídeo de novo — isso já foi decidido. Você só está marcando onde um novo subtema começa dentro do corte já definido.

## Destaques de frase (`highlights`)

0 a 2 citações que resumem o ponto mais forte do corte, para uso como texto de destaque na tela. A citação precisa existir literalmente na transcrição fornecida — nunca parafraseie nem invente. Se nenhuma frase se destacar o suficiente, retorne uma lista vazia.

## Conteúdo sensível

Se o capítulo tiver `Trecho para Validar Primeiro` e/ou `Observações` preenchidos no CSV, isso significa que uma afirmação feita no corte ainda não foi verificada. Nunca escreva uma intro, card ou destaque que apresente essa alegação como fato — mantenha a atribuição explícita à pessoa que falou.

## Neutralidade

Ao escrever qualquer texto (intro, cards), distinga sempre entre o que a pessoa no vídeo afirmou e o que é apresentado como fato pela transcrição. Prefira "Fulano afirma que..." a frases que deem a entender que algo aconteceu de fato, quando a transcrição só mostra que alguém disse isso.
