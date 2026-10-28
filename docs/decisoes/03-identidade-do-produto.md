# Identidade do produto por EAN e código de modelo

Aceita em outubro de 2026.

## Contexto

Para comparar o mesmo produto entre lojas é preciso reconhecer que "Smart TV LG 55 QNED 55QNED70BSA" e "TV LG 55QNED70BSA" são o mesmo item. Ao mesmo tempo, variantes diferem justamente em um detalhe: "128GB" e "256GB", "110V" e "220V".

## Decisão

Duas ofertas são o mesmo produto quando:

- têm o mesmo EAN; ou
- têm o mesmo código de modelo do fabricante e as mesmas especificações medidas (capacidade, polegadas, litros, BTU, voltagem).

Variantes de um modelo só se juntam quando todas são compatíveis entre si: "55 polegadas" junta com um título que omite o tamanho, mas "128GB", "256GB" e um título sem capacidade ficam separados, porque o último pode ser qualquer um dos dois. Títulos de peças e acessórios não usam o código de modelo, que nesses casos é do aparelho compatível ("Cuba da Air Fryer AF-55i").

## Alternativas rejeitadas

- Similaridade aproximada (MinHash, Jaccard, embeddings): junta títulos parecidos, que é o erro a evitar entre variantes.
- Agrupar só por EAN: poucas lojas preenchem o EAN, e quase nada seria agrupado.

## Consequências

Alguns produtos iguais ficam em grupos separados quando nenhum título traz EAN nem código. É preferível a mostrar como menor preço de um celular o preço da versão com menos memória.
