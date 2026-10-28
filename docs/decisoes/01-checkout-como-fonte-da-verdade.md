# O checkout da loja é a fonte da verdade

Aceita em outubro de 2026.

## Contexto

Comparadores mostram o preço do anúncio e, quando muito, uma estimativa de frete. O valor que a pessoa paga só aparece no carrinho: frete calculado para o CEP, desconto no Pix, parcelamento e, em algumas lojas, impostos que mudam conforme o estado de destino. Uma das lojas consultadas soma 6% de imposto para alguns estados, e isso não aparece em lugar nenhum antes do checkout.

## Decisão

Para cada oferta relevante, a API simula o carrinho na própria loja (endpoint público de simulação das lojas VTEX) com o CEP informado. Preço, Pix, parcelamento e frete vêm dessa resposta. O preço à vista é o valor que a etapa de pagamento cobra, que já inclui impostos.

- Uma simulação por oferta. Com vários itens no mesmo carrinho a loja rateia o frete, e o valor por item deixa de ser o que a pessoa pagaria comprando só ele.
- O selo de total exato só aparece quando o frete foi cotado para aquele CEP. Frete grátis anunciado, frete não informado e oferta vinda de comparador têm status próprio.
- Cotações ficam em cache por 5 minutos por loja, item, vendedor e CEP, compartilhadas entre buscas. O comprovante de cada frete (`cotado_em`, modalidade, transportadora, data prometida) guarda a hora da resposta da loja, e uma leitura do cache mantém essa hora.

## Alternativas rejeitadas

- Preço do catálogo com tabela de frete própria: erra impostos por estado e promoções de frete que só a loja conhece.
- Uma simulação com todas as ofertas da loja: metade das requisições, mas o frete rateado não corresponde a nenhuma compra real.

## Consequências

Uma busca fria faz centenas de requisições. Por isso só ofertas acima de um piso de relevância são cotadas, a concorrência por loja é limitada e a resposta chega em etapas ([decisão 4](04-um-processo-com-estado-em-memoria.md)). A suíte `testes/ao_vivo` confere amostras contra o checkout das lojas em cinco capitais, recalculando o total com uma fórmula escrita à parte.
