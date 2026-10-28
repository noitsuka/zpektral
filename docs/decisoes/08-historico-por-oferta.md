# Histórico de preço por oferta, na própria loja

Aceita em outubro de 2026.

## Contexto

Saber que uma geladeira custa R$ 1.899 hoje diz pouco. A pergunta de quem compra é se esse valor está bom para aquela loja: se a loja já vendeu mais barato no mês passado, se acabou de subir o preço antes de uma promoção, se o valor de hoje é o mais baixo em semanas.

O histórico que existia guardava preços por produto agrupado entre lojas (mesmo EAN ou código de modelo). Isso serve para comparar lojas, mas não responde à pergunta acima, e deixava de fora toda oferta sem grupo.

## Decisão

Cada busca grava, para toda oferta disponível com relevância de 70 ou mais, o preço do produto sob a chave da própria oferta: loja mais o código do item naquela loja (SKU, ASIN, id do anúncio). O mesmo preço da mesma oferta não é gravado de novo dentro de uma hora.

A rota `GET /historico/ofertas?ids=` devolve, para até 50 ofertas, o menor preço de cada dia nos últimos 90 dias, com o dia contado no horário de Brasília. A interpretação fica no site, porque depende do preço que está na tela agora:

- com menos de três dias anteriores, nada aparece;
- preço igual ou abaixo do menor do período, e abaixo da mediana, vira "menor preço desta loja em N dias";
- fora de uma faixa de 3% em torno da mediana, vira "X% abaixo" ou "X% acima do habitual desta loja";
- dentro da faixa, nada aparece na linha; o gráfico continua na conta.

Sem `DATABASE_URL`, a API grava num arquivo SQLite local, para que o histórico comece a se formar já na primeira execução. Em produção o banco é o PostgreSQL, com as migrações do Alembic.

## Alternativas rejeitadas

- Comparar com o preço de tabela que a loja informa ("de R$ 2.499 por R$ 1.899"): é o valor que a própria loja escolhe mostrar, e muitas vezes nunca foi praticado.
- Média em vez de mediana: uma única promoção relâmpago puxaria a média para baixo por semanas.
- Histórico de terceiros: não há fonte aberta com preço por loja e por item no Brasil.

## Consequências

O histórico começa vazio e ganha valor com o uso. Ofertas que a loja troca de código perdem o passado. O volume cresce com o número de buscas; a retenção de `DIAS_HISTORICO` (180 por padrão) apaga o que passa disso.
