# Um processo, com estado em memória

Aceita em outubro de 2026.

## Contexto

Uma busca fria consulta mais de 60 fontes e leva de 6 a 7 segundos, limitada pela loja mais lenta. A mesma busca repetida, ou mudada só nos filtros, não deveria consultar as lojas de novo.

## Decisão

- Cada busca (consulta normalizada, CEP) vira um trabalho compartilhado: requisições iguais e simultâneas esperam o mesmo trabalho, e o resultado fica em cache por 5 minutos. Filtros, ordenação e paginação rodam sobre o resultado em memória, em poucos milissegundos.
- O trabalho continua mesmo se o cliente desconectar, para não desperdiçar o esforço de quem chegar depois.
- `/busca` responde em até `espera_ms` (1,5 s por padrão) com o que já chegou e a lista de lojas pendentes. `/busca/transmissao` entrega cada loja por SSE assim que ela responde: primeiro os preços do catálogo, depois o frete do CEP.
- Os limites por endereço separam leitura do cache (barata) de busca nova (cara), e há um teto global de buscas em andamento, para a API não servir de amplificador de tráfego contra as lojas.

A API roda em um único processo uvicorn.

## Alternativas rejeitadas

- Vários workers: cada processo teria o próprio cache e os próprios limites, diluindo todos eles.
- Redis desde o início: mais uma peça para operar, sem ganho enquanto um processo assíncrono dá conta de uma carga que é quase toda espera de rede.

## Consequências

Para escalar horizontalmente, o próximo passo é mover o cache de buscas, o cache de cotações e os limites para o Redis, mantendo as mesmas interfaces.
