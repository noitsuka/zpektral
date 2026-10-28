# Importados com total estimado

Aceita em outubro de 2026.

## Contexto

Ofertas do eBay vêm em dólar, de vendedores fora do Brasil. O preço que se paga inclui o frete internacional, o imposto de importação e o ICMS do estado de destino, e esses impostos só são definidos pela Receita quando a encomenda chega. Em 2026 as regras mudaram duas vezes: a MP 1.357/2026 zerou o imposto de importação de compras de até US$ 50 dentro do Remessa Conforme, mas o eBay não participa do programa.

## Decisão

- Ofertas do eBay entram com origem `importado` e frete com status `estimado`. Nunca recebem o selo de total exato e ficam abaixo dos totais exatos e do frete grátis anunciado na ordenação por menor total.
- O dólar é a cotação de venda PTAX mais recente do Banco Central, guardada por 3 horas.
- O imposto de importação é 60% sobre produto mais frete em reais. O ICMS é calculado por dentro: (valor aduaneiro + imposto) ÷ (1 − alíquota) × alíquota. As duas alíquotas ficam na configuração (`ALIQUOTA_IMPOSTO_IMPORTACAO`, `ALIQUOTA_ICMS_IMPORTACAO`), porque mudam por lei e por estado.
- Cada oferta mostra a conta inteira: preço e frete em dólar, cotação usada, imposto de importação e ICMS.
- A busca só pede anúncios que entregam no Brasil (`deliveryCountry:BR`) e informa o CEP ao eBay, para que o frete venha calculado para o destino.

## Alternativas rejeitadas

- Mostrar só o preço convertido: esconde até 2,5 vezes o valor em impostos.
- Usar a regra do Remessa Conforme: o eBay não está no programa.
- Misturar com os totais exatos: quebraria a garantia de que "total exato" é o que o checkout cobra.

## Consequências

A comparação global fica possível, com o custo de uma estimativa que pode errar a taxa dos Correios e mudanças de alíquota ainda não refletidas na configuração. Quem quiser só valores exatos usa o filtro "Só total exato".
