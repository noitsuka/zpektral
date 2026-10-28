# Auditoria de cotações

Aceita em outubro de 2026.

## Contexto

Ao conferir os totais contra as lojas, apareceu um checkout que responde ao mesmo carrinho com valores diferentes: em 12 chamadas idênticas, 6 vieram com 8% de imposto e 6 sem, provavelmente servidores com configurações diferentes atrás do mesmo endereço. Depois, com as duas cotações da auditoria saindo de fato em paralelo, surgiram dois outros padrões: vendedores parceiros de marketplace que devolvem transportadoras e fretes diferentes a cada chamada (R$ 16,70 numa, R$ 757,05 na seguinte), e respostas que chegam incompletas, sem nenhuma opção de entrega, enquanto a chamada gêmea vem completa.

## Decisão

- As primeiras 20 cotações de cada loja, e depois 5% delas, são feitas em dobro e em paralelo.
- Se só uma das duas respostas tem frete cotado, a outra falhou dentro da loja: vale a completa, e isso não conta como divergência.
- Se as duas têm frete cotado e os valores diferem, o vendedor daquela loja passa a ser tratado como instável: toda cotação dele é feita em dobro, o valor mostrado é o maior dos dois e a oferta recebe o alerta `preco_instavel`, perdendo o selo de total exato. Os outros vendedores da mesma loja continuam com o selo.
- Lojas cujo checkout inteiro varia ficam marcadas como instáveis no cadastro (`instavel` em `lojas_vtex.json`).
- Uma vez instável, o vendedor não volta a ter totais exatos, nem quando as duas respostas coincidem: com duas respostas possíveis, coincidir pode ser sorte.

## Alternativas rejeitadas

- Cotar tudo em dobro: dobra a carga sobre as lojas para detectar um problema raro.
- Mostrar o menor valor: promete um preço que a loja pode não cobrar.
- Marcar a loja inteira na primeira divergência: um parceiro instável na Americanas tirava o selo de todas as ofertas da própria Americanas.

## Consequências

O custo é de 20 simulações extras por loja e, depois disso, 5% a mais. Em troca, a API nunca apresenta como exato um valor que a própria loja não sustenta, e um parceiro instável não contamina o resto da loja.
