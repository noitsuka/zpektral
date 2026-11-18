# Fontes de preço

Estado medido em 17 de novembro de 2026. As lojas VTEX foram sondadas com `scripts/sondar_lojas_vtex.py`; Amazon, KaBuM! e Buscapé, com uma busca pelo próprio `ServicoBusca`.

## Estados de uma fonte

Cada busca devolve um relatório por fonte (`fontes` em `/busca`, eventos `lote` e `falha_fonte` em `/busca/transmissao`) com um destes valores em `status`:

| `status` | Quando |
| --- | --- |
| `ok` | a loja respondeu |
| `erro` | resposta inesperada, HTTP 4xx fora de 401/403/429, 5xx ou falha de rede |
| `tempo_esgotado` | a loja passou do limite de tempo da fonte |
| `bloqueada` | HTTP 401, 403 ou 429, ou página de verificação de robô; a mensagem é "a loja recusou o acesso automatizado" |
| `desativada` | fonte que depende de credenciais ainda não configuradas |

O evento `falha_fonte` sai para `erro`, `tempo_esgotado` e `bloqueada`; o cliente distingue pelo campo `fonte.status`.

Em `/lojas`, `saude.estado` resume as últimas buscas de cada fonte:

| `estado` | Quando |
| --- | --- |
| `saudavel` | a última resposta foi `ok` |
| `degradada` | três falhas seguidas |
| `bloqueada` | a última falha foi um bloqueio; muda na primeira recusa, sem esperar três |
| `desativada` | sem credenciais |
| `sem_dados` | a fonte ainda não respondeu desde que a API subiu |

A entrada e a saída de `degradada` e de `bloqueada` disparam o webhook de alerta, quando configurado. Nenhum bloqueio é contornado: a fonte fica `bloqueada` até a loja voltar a responder.

## Fontes atuais

| Fonte | Como entra | O que entrega | Estado medido |
| --- | --- | --- | --- |
| 95 lojas VTEX | busca inteligente ou catálogo legado, e simulação do carrinho | preço do carrinho, estoque, frete e prazo por CEP, Pix, parcelamento, EAN | aprovadas em duas rodadas da sonda |
| Amazon | página pública de busca (`/s?k=`) | preço, preço de tabela, parcelamento, imagem, frete grátis anunciado; sem frete por CEP | `ok`, 55 ofertas para "air fryer" |
| KaBuM! | catálogo público | preço, Pix, parcelamento, frete grátis anunciado; sem frete por CEP | `ok`, 60 ofertas para "fone bluetooth" e nenhuma para "air fryer" |
| Buscapé | página pública de busca e de produto | menor preço por loja, origem `comparador`, sem frete | `ok`, 68 ofertas para "air fryer" |
| Mercado Livre | API oficial | preço e frete por CEP | `desativada`, sem credenciais |
| Shopee | API de afiliados | preço e link de afiliado; frete só pelo navegador opcional | `desativada`, sem credenciais |
| eBay | API Browse | preço em dólar, frete para o Brasil e imposto estimado | `desativada`, sem credenciais |

### Lojas VTEX por segmento

| Segmento | Lojas | Nomes |
| --- | --- | --- |
| Geral | 2 | Americanas, Carrefour |
| Eletro | 16 | Arno, Brastemp, Cadence, Climario, Compra Certa, Consul, Electrolux, Elgin, KitchenAid, Lojas MM, Mallory, Mondial, Obabox, Oster, Walita, WebContinental |
| Tecnologia | 5 | Fujioka, iByte, Intelbras, Motorola, Multi |
| Casa | 5 | Altenburg, Brinox, Imaginarium, Karsten, Trousseau |
| Construção | 6 | Obramax, Quero-Quero, Rede Construir, Telhanorte, Todimo, Tumelero |
| Moda e calçados | 23 | Bebecê, Bottero, Brandili, C&A, Calvin Klein, Constance, Dakota, Democrata, Dudalina, Ferracini, Hering, Hope, John John, Le Lis, Levi's, Malwee, Polo Wear, Pompéia, Puket, Quiksilver, Ramarim, Reserva, Usaflex |
| Esporte | 8 | Artwalk, Asics, Authentic Feet, Mizuno, Olympikus, Penalty, Track&Field, Under Armour |
| Beleza | 3 | Época Cosméticos, Ikesaki, Mahogany |
| Farmácia | 8 | Drogal, Drogaria Catarinense, Drogaria Globo, Drogaria São Paulo, Drogaria Venancio, Drogarias Pacheco, Drogasmil, Farmácia Indiana |
| Mercado | 6 | Atacadão, GBarbosa, Giassi, Prezunic, Sam's Club, Savegnago |
| Joias e relógios | 7 | H.Stern, Mondaine, Monte Carlo, Morana, Rommanel, Seculus, Vivara |
| Ótica | 2 | eÓtica, Óticas Diniz |
| Pet | 1 | Cobasi |
| Papelaria e livros | 1 | Livrarias Curitiba |
| Auto | 1 | DPaschoal |
| Brinquedos | 1 | Ri Happy |

Configurações que não são o padrão:

- Só busca inteligente (`"busca": "is"`), porque o robots.txt proíbe o catálogo legado ou porque a loja só responde nela: Arno, Asics, Brinox, C&A, Carrefour, Hope, Ikesaki, Malwee, Mondial, Reserva, Trousseau.
- Só catálogo legado (`"busca": "legacy"`): Cadence, Drogal, Época Cosméticos, H.Stern, Intelbras (o robots proíbe a busca inteligente), Livrarias Curitiba, Monte Carlo, Seculus, Track&Field (idem), Under Armour.
- Canal de vendas próprio (`"sc"`), o mesmo do link de carrinho da loja: Oster (2) e Calvin Klein (18).
- Redes regionais, que respondem "não entrega" para outros estados e foram aprovadas com CEP da região: Drogaria Venancio, Drogasmil e Prezunic (20040-002, Rio de Janeiro), Farmácia Indiana (30130-010, Belo Horizonte), Savegnago (14010-000, Ribeirão Preto), Giassi (88010-400, Florianópolis), GBarbosa (49010-000, Aracaju), Drogaria Globo (64000-020, Teresina, e 65010-000, São Luís).

### Sondagem de novembro de 2026

A sonda lê o robots.txt pela RFC 9309 (curingas, `$`, grupos com vários `User-agent`, grupo próprio do `zpektral` e a regra mais longa entre `Allow` e `Disallow`) contra as URLs que o app monta, e não pede caminho proibido. robots.txt com 5xx ou 429 conta como proibição total. Depois busca um termo do segmento, simula o carrinho de até três itens que tenham estoque e aprova a loja que devolve ao menos uma opção de entrega. Rodou com até quatro lojas em paralelo e o user agent `zpektral/0.1`, sem guardar cookies.

```bash
cd backend
python -m scripts.sondar_lojas_vtex app/dados/lojas_vtex.json --paralelas 4
python -m scripts.sondar_lojas_vtex regionais.json --cep 20040002
pytest -m live testes/ao_vivo/teste_robots.py
```

`regionais.json` não está no repositório: é uma lista à parte, no formato de `lojas_vtex.json`, só com as lojas da região do CEP.

Lista atual (58 lojas antes da mudança):

| Resultado | Lojas |
| --- | --- |
| Aprovadas como estavam | 41 |
| Aprovadas com ajuste | Arno, Asics, C&A, Malwee, Mondial, Reserva e Trousseau (robots proíbe o catálogo legado), Intelbras (robots proíbe a busca inteligente com `page=`), Oster (canal 2), DPaschoal, Época e Venancio (termo do segmento ou CEP da região) |
| Removidas | Chilli Beans, Extrafarma e Pague Menos (robots proíbe `/api/checkout`, por `*/checkout*` e `/*order*`), Speedo (robots.txt responde 429), Aramis (nenhum item com estoque na busca) |

As cinco removidas falharam do mesmo jeito em três execuções.

Candidatas novas (220, nenhuma das 58 atuais, das sete que saíram em outubro nem das 13 citadas na sondagem anterior):

| Resultado | Quantas | Lojas |
| --- | --- | --- |
| Aprovadas nas duas rodadas | 42 | as novas da tabela por segmento |
| robots.txt proíbe as APIs | 46 | Alô Bebê, Animale, Avon, Balaroti, Bemol, Bibi, Bistek, Canal da Peça, Comper, Condor, Converse, Coza, Ellus, Eletrosom, Estrela, Farm, Ferramentas Kennedy, Fila, Fort Atacadista, Granado, Havaianas, Hortifruti, Kärcher, Lojas Becker, Lupo, Martinello, Novo Mundo, Osklen, Oxford, Pampili, Pandora, Piccadilly, Richards, Riachuelo, São João, Shoulder, Stanley, Super Muffato, Super Nosso, Technos, Tupperware, Ultrafarma, Umbro, Drogaria Minas Brasil, Zaffari, Zee.Dog |
| Bloqueio (HTTP 401, 403 ou 429) | 25 | Araujo, Berlanda, Carajás, Casio, Cassol, Colcci, Deca, Dolce Gusto, Droga Raia, JBL, Jocar, Lebes, MMartan, Nestlé Até Você, Óticas Carol, Onofre, Panvel, Petlove, PneuStore, Sephora, Tip Top, Topper, Zattini; e Max Titanium e Jequiti no checkout |
| Não respondem como VTEX (404) | 59 | entre elas Arezzo, Decathlon, Marisa, Natura, Pão de Açúcar, Pernambucanas, Positivo, Vans, Westwing |
| API sem JSON | 16 | Azaleia, Colormaq, Dzarm, Empório da Cerveja, Koerich, Leitura, Loja do Mecânico, Maria Filó, Mor, Pegada, QÓculos, Shoptime, Sonda, Taqi, Torra, Tricae |
| Falha de conexão ou tempo | 28 | entre elas Boticário, C&C, Midea, Submarino, Tramontina |
| robots.txt com 5xx | 2 | Cybelar, Passarela |
| Sem frete ou sem estoque | 2 | Drogaria Rosário (não entrega nem em Brasília), Bretas (nada com estoque) |

## Fontes autorizadas: pesquisa

Lida nas páginas oficiais em novembro de 2026. Onde a página recusou leitura automatizada ou só carrega com JavaScript, está marcado como não verificado. Nenhum conector novo foi escrito, porque todos dependem de conta ou credencial que o projeto ainda não tem.

### Mercado Livre (já integrado)

- Entrega: busca e frete por CEP (`/items/{id}/shipping_options?zip_code=`), já usados por `app/fontes/mercadolivre.py`.
- Não verificado: a documentação em developers.mercadolivre.com.br respondeu 403 à leitura automatizada. Pela busca na web, a página de erro 403 cita escopos inválidos como causa; o app já explica esse caso ("confira se o app tem acesso à busca") e o marca como `bloqueada`.
- Passos do dono, como o projeto já espera:
  1. Criar um app em https://developers.mercadolivre.com.br/devcenter com um endereço de redirecionamento `https` que você controle.
  2. Em `backend`, rodar `python -m scripts.autorizar_mercadolivre`, informar App ID, Client Secret e o redirecionamento, abrir o link, autorizar e colar o endereço de volta.
  3. O script grava `ML_ID_CLIENTE`, `ML_SEGREDO_CLIENTE` e `ML_TOKEN_RENOVACAO` em `backend/.env` e o token em `.ml-token.json`. Em produção, as três variáveis vão para o projeto da API na Vercel.
- Ponto a conferir na documentação: o app grava o token renovado em `ML_ARQUIVO_TOKEN`, e o disco da Vercel não persiste. Se o token de renovação for de uso único, a produção precisa guardar o token em outro lugar.

### Amazon (Creators API)

- A PA-API 5.0 foi descontinuada e trocada pela Creators API; chamadas à PA-API voltam 403, e as chaves antigas não servem ([deprecação](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation), [migração](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/migrating-to-creatorsapi-from-paapi)).
- Brasil (`www.amazon.com.br`) está entre os mercados suportados ([locales](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/locale-reference)).
- Requisitos: conta de Associados aceita e pelo menos 10 vendas qualificadas nos últimos 30 dias; sem vendas por 30 dias seguidos, o acesso é suspenso até a próxima venda enviada ([introdução](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction), [limites](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/api-rates)).
- Custo: nenhum preço publicado. Limite inicial de 1 requisição por segundo e 8.640 por dia, que cresce com a receita gerada.
- Entrega: preço, preço de referência e economia, tipo e texto de disponibilidade, vendedor, condição, oferta em destaque. Não há frete, prazo nem Prime, e o preço vem calculado para um endereço padrão do país ([OffersV2](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/offersV2)). Para o zpektral, troca a leitura do HTML por dados oficiais, mas continua sem frete por CEP.
- Restrições do contrato do Associados Brasil ([contrato](https://associados.amazon.com.br/help/operating/agreement), [políticas](https://associados.amazon.com.br/help/operating/policies)): preço e disponibilidade só podem ser exibidos com dados da API ou link fornecido pela Amazon; em comparação com outras lojas, é preciso mostrar o menor preço novo da Amazon; não revender nem redistribuir o conteúdo. A página de políticas veio truncada na leitura; a parte sobre cache de até 24 horas, data e hora junto do preço e o aviso de que preços podem mudar foi lida só por resumo e precisa ser conferida.
- Passo do dono: entrar no Associados Brasil, chegar a 10 vendas em 30 dias e criar a credencial em Associates Central, Tools, Creators API, Create Application (Credential ID, Secret e versão; OAuth 2.0 com token de uma hora).

### Magazine Luiza

- Programa próprio, o Parceiro Magalu, com comissão de até 12% ([parceiromagalu.com.br](https://www.parceiromagalu.com.br/)). Nenhuma API ou feed de produtos para afiliados encontrado.
- As APIs de [developers.magalu.com](https://developers.magalu.com/) são para vendedores e integradoras: preço e estoque do próprio portfólio, com escopos de seller. Não expõem o catálogo público nem frete por CEP.
- Passo do dono: nenhum que traga dados hoje. A Magalu continua aparecendo pelo Buscapé e como vendedora dentro da Americanas.

### Grupo Casas Bahia (Casas Bahia, Ponto, Extra)

- A página oficial de afiliados respondeu 403 à leitura automatizada, e o perfil do anunciante na Awin só abre com login. Pela busca na web, o programa roda na Awin.
- A Awin documenta feeds de produto para publishers, com comparadores de preço citados como o público principal. As colunas incluem `price`, `product_price_old`, `in_stock`, `stock_quantity`, `delivery_cost`, `delivery_time`, `ean`, `deep_link` e `last_updated`; o frete é um valor fixo, sem CEP ([colunas](https://help.awin.com/developers/docs/hosting-feeds), [feeds](https://help.awin.com/developers/docs/product-feed-publisher-guide-intro.md)).
- Não verificado: se a Casas Bahia publica feed na Awin e o que os termos dela dizem sobre comparadores.
- Passo do dono: criar conta de publisher na Awin, pedir entrada no programa da Casas Bahia e conferir no painel se há feed de produtos. Com feed, as ofertas entrariam sem frete por CEP, como o Buscapé.

### MadeiraMadeira

- `/afiliados` não existe (404) e a página inicial não tem link de afiliados, parceiros ou API. Nada encontrado.

### Leroy Merlin

- A página oficial do programa respondeu 403. Uma notícia de outubro de 2024 ([GiroNews](https://gironews.com/construcao/leroy-merlin-lanca-programa-de-afiliados-para-profissionais/)) diz que o programa usa a Rakuten Advertising, é voltado a profissionais e influenciadores e paga de 3% a mais de 10%.
- Não verificado: feed ou API de produtos. A página de Product Search da Rakuten não carregou o conteúdo.
- Passo do dono: cadastro de publisher na Rakuten Advertising (signup.linkshare.com) e pedido de entrada no programa.

### Shopee (já integrada)

- O app usa a Open API de afiliados (GraphQL em `open-api.affiliate.shopee.com.br`, consulta `productOfferV2`, assinatura SHA-256 com App ID, instante, corpo e segredo): preço mínimo e máximo, desconto, loja e link de afiliado, sem frete por CEP.
- Não verificado: as páginas de afiliados só carregam com JavaScript, e open.shopee.com recusou a leitura.
- Passo do dono: conta em affiliate.shopee.com.br, pedido de acesso à Open API no painel e `SHOPEE_ID_APP` e `SHOPEE_SEGREDO` no ambiente da API.

### AliExpress

- Não verificado: o portal de afiliados e a documentação da API só carregam com JavaScript, e a página de documentação antiga respondeu 500. Envio para o Brasil, moeda em reais e frete por CEP ficam sem confirmação. Se entrar, seria como o eBay, com imposto de importação estimado.

### Redes de afiliados

| Rede | Produtos | Requisitos e custo | Verificado |
| --- | --- | --- | --- |
| Awin | feed CSV ou XML por anunciante, com preço, estoque, frete fixo, EAN e deep link; API REST para publishers | conta de publisher e aprovação por anunciante; custo não informado | colunas e uso por comparadores |
| Rakuten Advertising | menu da API lista Product Search | cadastro de publisher | conteúdo da página não carregou |
| Admitad | documentação em developers.mitgo.com | | respondeu 403 |
| Lomadee | nenhuma API ou feed de produtos na página; developer.lomadee.com não existe | cadastro grátis, CNPJ opcional | página inicial |

### Fornecedores comerciais

| | SerpApi (Google Shopping) | DataForSEO (Merchant) |
| --- | --- | --- |
| Brasil | `gl=br` suportado; localização por cidade, sem CEP | código do Brasil não verificado; a página comercial fala em CEP e coordenadas |
| Por oferta | título, loja, preço, avaliação, texto de entrega; sem estoque, preço antigo ou frete por CEP | título, preço, avaliação e domínio na documentação lida |
| Preço | grátis 250 buscas por mês; US$ 25 por 1.000, US$ 75 por 5.000, US$ 150 por 15.000 | pré-pago, mínimo de US$ 50; US$ 0,001 por produto na fila padrão (até 45 min) e US$ 0,002 na prioritária (até 1 min) |
| Termos | proíbe reproduzir ou revender o serviço sem permissão escrita; proteção jurídica só a partir do plano de US$ 150 e só nos EUA | dados do Google não podem ser usados para competir com o buscador ou prejudicá-lo, o que pesa contra um comparador |
| Fontes | [API](https://serpapi.com/google-shopping-api), [preços](https://serpapi.com/pricing), [termos](https://serpapi.com/legal) | [API](https://docs.dataforseo.com/v3/merchant/google/products/task_post/), [preços](https://dataforseo.com/apis/merchant-api), [termos](https://dataforseo.com/terms-of-service) |

Nenhum dos dois traz frete por CEP; as ofertas entrariam como origem `comparador`, sem total exato, e pedem leitura jurídica antes do uso público.

## O que depende do dono

1. Mercado Livre: criar o app e rodar `scripts.autorizar_mercadolivre`; conferir como guardar o token renovado na Vercel.
2. Shopee: pedir acesso à Open API de afiliados e configurar as duas variáveis.
3. Amazon: entrar no Associados Brasil e gerar 10 vendas em 30 dias para liberar a Creators API.
4. Casas Bahia, Ponto e Extra: conta de publisher na Awin e entrada no programa; conferir se há feed.
5. Leroy Merlin: conta de publisher na Rakuten Advertising e entrada no programa.
6. SerpApi ou DataForSEO: só depois de leitura jurídica dos termos, e com orçamento mensal.
