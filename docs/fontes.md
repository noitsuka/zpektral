# Fontes de preço

Estado medido em 17 de novembro de 2026 e revisto em 19 de novembro (Fast Shop, Mercado Livre, Shopee e redes de afiliados). As lojas VTEX foram sondadas com `scripts/sondar_lojas_vtex.py`; Amazon, KaBuM! e Buscapé, com uma busca pelo próprio `ServicoBusca`.

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
| 96 lojas VTEX | busca inteligente ou catálogo legado, e simulação do carrinho | preço do carrinho, estoque, frete e prazo por CEP, Pix, parcelamento, EAN | aprovadas em duas rodadas da sonda |
| Amazon | página pública de busca (`/s?k=`) | preço, preço de tabela, parcelamento, imagem, frete grátis anunciado; sem frete por CEP | `ok`, 55 ofertas para "air fryer" |
| KaBuM! | catálogo público | preço, Pix, parcelamento, frete grátis anunciado; sem frete por CEP | `ok`, 60 ofertas para "fone bluetooth" e nenhuma para "air fryer" |
| Buscapé | página pública de busca e de produto | menor preço por loja, origem `comparador`, sem frete | `ok`, 68 ofertas para "air fryer" |
| Mercado Livre | API oficial: catálogo (`/products/search`) e ofertas de cada produto | preço, preço anterior informado, vendedor, marca, GTIN, frete por CEP | `desativada`, sem credenciais; fora do histórico de preços |
| Shopee | API de afiliados | preço da versão mais barata, faixa de preço por versão, loja e link de afiliado; sem frete | `desativada`, sem credenciais |
| eBay | API Browse | preço em dólar, frete para o Brasil e imposto estimado | `desativada`, sem credenciais |

Amazon na Vercel (`gru1`), em 18/11/2026: 8 de 8 buscas pela API de homologação trouxeram a Amazon com `ok`, entre 1,0 e 2,8 s (47 e 48 ofertas nas duas primeiras). As falhas vistas antes foram intermitentes, e o plano Hobby guarda os logs da função só por 30 minutos, então a causa delas não ficou registrada. Página 200 sem nenhum resultado devolve zero ofertas (antes quebrava a leitura e virava `erro`), e o 503 com a página de robô da Amazon sai como `bloqueada`.

### Lojas VTEX por segmento

| Segmento | Lojas | Nomes |
| --- | --- | --- |
| Geral | 2 | Americanas, Carrefour |
| Eletro | 17 | Arno, Brastemp, Cadence, Climario, Compra Certa, Consul, Electrolux, Elgin, Fast Shop, KitchenAid, Lojas MM, Mallory, Mondial, Obabox, Oster, Walita, WebContinental |
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

### Sondagem de 19 de novembro de 2026

Busca de lojas de móveis, eletro, informática, construção e casa, com a mesma sonda (robots.txt pela RFC 9309, busca e simulação do carrinho) e quatro lojas em paralelo.

| Resultado | Lojas |
| --- | --- |
| Entrou | Fast Shop, em `site.fastshop.com.br` (o `www` responde 503 no robots.txt): aprovada com CEP de São Paulo e de Belo Horizonte |
| Aprovada e deixada de fora | Poloar: a busca inteligente da loja devolve quase só multi-splits da Fujitsu, que passavam como 12.000 BTU pelo "(2x 12.000)" do título; mais anúncios sem ganho de precisão |
| robots.txt proíbe as APIs | Britânia, Casa&Video, Madesa (a simulação), Mobly, Philco, Polishop, Samsung (a simulação) |
| Bloqueio (403) | Kalunga |
| Não respondem como VTEX | Black+Decker, Camicado, Colombo, Dufrio, Dutra Máquinas, eFácil, Esmaltec, Etna (encerrou em 2022), Ferreira Costa, Fischer, Frigelar (Oracle Commerce), Gazin, Havan (Magento), Leroy Merlin, Leveros, Lojas KD, Nagem, Suggar, Tok&Stok, WAP, Zema (Oracle Commerce) |
| Falha de conexão | C&C (vendida em 2023), Girafa, Ricardo Eletro, Vonder |

Medição da Fast Shop nas 77 buscas julgadas, com as mesmas respostas gravadas para as outras lojas (`avaliar_busca.py rodar --lojas` com o cadastro antigo). Sem ela no cadastro, a Fast Shop continua aparecendo pelo Buscapé, como na produção de hoje; o filtro de `--lojas` passou a valer antes de o Buscapé saber quais lojas são diretas, porque na primeira medição ela sumia dos dois lados e o ganho saía inflado (0,845 para 0,889).

| | cobertura | precisão | p@5 | MRR | lojas com relevante | requisições por busca |
| --- | --- | --- | --- | --- | --- | --- |
| Fast Shop pelo Buscapé | 0,846 | 0,883 | 0,947 | 0,978 | 9,08 | 122,7 |
| Fast Shop direta | 0,884 | 0,884 | 0,949 | 0,978 | 9,35 | 124,7 |

Pelo Buscapé ela aparecia em 55 ofertas exibidas; direta, em 648, distribuídas por 38 das 77 buscas, quase todas do produto pedido, com frete e estoque por CEP. Nenhuma busca perdeu oferta exibida.

Conferida na Vercel em 19/11/2026, num preview da API em `gru1` (sem banco, apagado depois), com CEP 01310-100: "air fryer" 32 ofertas, todas relevantes, em 11,5 s na primeira busca da instância (20 com frete calculado, 12 sem cotação no prazo); "geladeira frost free" 31 ofertas, todas com frete calculado, em 4,7 s; "smart tv 55" 30 ofertas (25 relevantes com frete) em 5,0 s, a fonte mais lenta dessa busca, cerca de 1,6 s depois da segunda; "fone bluetooth jbl" sem CEP, 30 ofertas em 2,8 s. Nenhuma recusa. Na produção, as mesmas quatro buscas não mostraram nenhuma oferta da Fast Shop pelo Buscapé. Se a loja passar a recusar a Vercel, as ofertas dela somem, porque o Buscapé descarta loja direta; o estado `bloqueada` em `/lojas` avisa. Os deslizes vistos são da régua de relevância que vale para todas as lojas: notebook "com SSD de 1 TB" em "ssd 1tb nvme" e Kindle Scribe em "kindle paperwhite", ambos com nota entre 70 e 76.

A estante Multy (Artely) continua só em Amazon, Buscapé (Magazine Luiza), WebContinental, Americanas, Carrefour e Tumelero. As outras lojas que a vendem são Casas Bahia, Ponto, Extra e MadeiraMadeira, nenhuma acessível sem contornar proteção ou contrariar o robots.txt, e o Mercado Livre, que depende da autorização.

## Fontes autorizadas: pesquisa

Lida nas páginas oficiais em novembro de 2026. Onde a página recusou leitura automatizada, a leitura foi pela cópia do Web Archive ou pelos arquivos JavaScript públicos do próprio portal, e está dito qual. O que não foi confirmado está marcado como não verificado. Nenhum conector novo foi escrito, porque todos dependem de conta, aprovação ou contrato que o projeto ainda não tem.

### Mercado Livre (integrado, aguardando autorização)

Documentação lida pelas cópias do Web Archive de developers.mercadolivre.com.br (o site responde 403 à leitura automatizada), de 2025 a agosto de 2026.

- **Busca por palavra-chave:** `/sites/MLB/search?q=` saiu da documentação em 07/04/2025 ([itens e buscas](https://web.archive.org/web/20250523103622/https://developers.mercadolivre.com.br/pt_br/itens-e-buscas)) e responde 403 mesmo com token válido; há relatos públicos de desenvolvedores até outubro de 2026, sem motivo oficial. Sem token, conferido em 19/11/2026: `{"message":"forbidden","status":403}`.
- **Caminho que o conector usa:** `/products/search?status=active&site_id=MLB&q=` (catálogo: nome, marca, GTIN e fotos, sem preço) e, para até 6 produtos que casam com a busca, `/products/{id}/items` (as ofertas que disputam a página do produto: preço, `original_price`, vendedor, condição e frete grátis). Entram as 3 ofertas novas mais baratas de cada produto. O vendedor vem de `/users?ids=`; se falhar, a oferta fica sem nome. Os dois recursos ficam sob a permissão funcional "Publicação e sincronização"; sem ela, a resposta é 403 `PA_UNAUTHORIZED_RESULT_FROM_POLICIES`, e a fonte sai como `bloqueada` com essa explicação ([permissões](https://web.archive.org/web/20260813152447/https://developers.mercadolibre.com.ar/es_ar/permisos-funcionales), [catálogo](https://web.archive.org/web/20260817170934/https://developers.mercadolibre.com.co/en_us/products-search), [ofertas do produto](https://web.archive.org/web/20250804054810/https://developers.mercadolivre.com.br/pt_br/concorrencia-em-catalogo)).
- **Limitações:** só aparecem produtos de catálogo; anúncio fora do catálogo não é encontrado. Desde 12/05/2025 `/products/{id}` não traz mais preço, por isso as ofertas vêm de `/items` do produto. Chamadas por busca: 1 no catálogo, até 6 nas ofertas, 1 nos vendedores e até 18 no frete (6 produtos com 3 ofertas). Limite de requisições não publicado; 429 vira `bloqueada`.
- **Frete:** `/items/{id}/shipping_options?zip_code=` continua documentado e é uma estimativa para uma unidade ([custos de envio](https://web.archive.org/web/20250216094738/https://developers.mercadolivre.com.br/pt_br/custos-de-envio-e-sla)). Não foi possível confirmar que responde a um app que não é o vendedor.
- **OAuth:** `authorization_code`, access token de 6 horas, refresh token de uso único (cada renovação devolve outro), válido por 6 meses, invalidado por troca de senha, troca do Client Secret, revogação ou 4 meses sem chamadas. É preciso marcar `offline_access` no app para receber o refresh token. PKCE é opcional ([autenticação](https://web.archive.org/web/20250804064557/https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao)).
- **Como o token é guardado:** a tabela `credenciais_oauth` (migração `0004`) guarda o par de tokens cifrado com AES-GCM pela `CHAVE_CREDENCIAIS`. Uma trava consultiva do PostgreSQL faz uma instância renovar por vez, a renovação não é cancelada junto com a busca, e o `ML_TOKEN_RENOVACAO` do ambiente é a semente. Cada semente tem a própria linha (`mercadolivre:<resumo da semente>`): trocar a variável começa outra cadeia, e um deploy antigo, num rollback, continua achando a dele. Se a gravação falhar depois de o Mercado Livre trocar o token, o cofre grava de novo numa transação nova; ele nunca reapresenta um refresh token já trocado, porque o Mercado Livre pode revogar a cadeia inteira. Com banco e sem chave válida, a fonte fica desativada. Restaurar o banco a partir de um branch antigo traz um token já trocado: é preciso autorizar de novo.
- **Termos da API** ([termos](https://web.archive.org/web/20250607191142/https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes)): conteúdo exibido atualizado ao menos a cada 24 horas (6 horas para listas de anúncios), só cópias intermediárias (2.2.1.3), proibido armazenar conteúdo para serviço concorrente (7.4) e scraping (7.6). O cache de busca do zpektral é de 5 minutos, e as ofertas do Mercado Livre não entram no histórico de preços (`FONTES_SEM_HISTORICO`). Não há proibição nominal de comparador; a leitura jurídica fica com o dono.
- **Programa de afiliados:** sem API nem feed de produtos, e os termos proíbem publicidade comparando produtos (5.3) e extração automatizada (4.3c). Não serve ao comparador.
- **Passos do dono:**
  1. Criar o app em https://developers.mercadolivre.com.br/devcenter com escopos `read` e `offline_access` (sem `write`), a permissão funcional "Publicação e sincronização" e um redirecionamento `https` que você controle.
  2. Aplicar a migração `0004` na produção (`docs/implantacao.md`, seção 7).
  3. Em `backend`, rodar `python -m scripts.autorizar_mercadolivre --vercel`, entrar com a conta que autoriza (administradora), colar o endereço de volta. O script grava as quatro variáveis como sensíveis só em Production; nada passa pela tela.
  4. Fazer o deploy de produção da API e conferir uma busca.
  5. Para uso local, criar um segundo app no devcenter e rodar o script sem `--vercel` (grava o `backend/.env`; o banco local precisa estar na `0004`). A documentação não diz se o Mercado Livre mantém duas autorizações do mesmo app e usuário ao mesmo tempo; com um app só, autorizar no computador pode derrubar a produção.
- Não verificado sem credenciais: se `/items/{id}/shipping_options` responde a um app que não é o vendedor, o limite de ids de `/users?ids=` e se o link `https://produto.mercadolivre.com.br/MLB-<número>-_JM` abre sem o nome do produto. O teste `pytest -m live testes/teste_mercadolivre.py` confere a busca com o cofre local.
- **Revogar:** revogar o acesso do app na conta que autorizou ou trocar o Client Secret (os dois invalidam os tokens, pela documentação de autenticação), apagar as linhas com `delete from credenciais_oauth where fonte like 'mercadolivre:%'` e remover as quatro variáveis da Vercel.

### Amazon (Creators API)

- A PA-API 5.0 foi descontinuada e trocada pela Creators API; chamadas à PA-API voltam 403, e as chaves antigas não servem ([deprecação](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation), [migração](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/migrating-to-creatorsapi-from-paapi)).
- Brasil (`www.amazon.com.br`) está entre os mercados suportados ([locales](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/locale-reference)).
- Requisitos: conta de Associados aceita e pelo menos 10 vendas qualificadas nos últimos 30 dias; sem vendas por 30 dias seguidos, o acesso é suspenso até a próxima venda enviada ([introdução](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction), [limites](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/api-rates)).
- Custo: nenhum preço publicado. Limite inicial de 1 requisição por segundo e 8.640 por dia, que cresce com a receita gerada.
- Entrega: preço, preço de referência e economia, tipo e texto de disponibilidade, vendedor, condição, oferta em destaque. Não há frete, prazo nem Prime, e o preço vem calculado para um endereço padrão do país ([OffersV2](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/offersV2)). Para o zpektral, troca a leitura do HTML por dados oficiais, mas continua sem frete por CEP.
- Restrições do contrato do Associados Brasil ([contrato](https://associados.amazon.com.br/help/operating/agreement), [políticas](https://associados.amazon.com.br/help/operating/policies)): preço e disponibilidade só podem ser exibidos com dados da API ou link fornecido pela Amazon; em comparação com outras lojas, é preciso mostrar o menor preço novo da Amazon; não revender nem redistribuir o conteúdo. A página de políticas veio truncada na leitura; a parte sobre cache de até 24 horas, data e hora junto do preço e o aviso de que preços podem mudar foi lida só por resumo e precisa ser conferida.
- Revisto em 19/11/2026: `SearchItems` aceita até 10 itens por chamada, filtro de preço e de entrega (Prime, frete grátis), sem custo de frete nem CEP ([SearchItems](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/operations/search-items)). Cache recomendado de 1 hora para ofertas; as políticas do Associados Brasil (atualizadas em 14/04/2026) limitam o cache a 24 horas, proíbem guardar imagens e pedem data e hora junto do preço quando a atualização for menos que horária. Só o titular da conta cadastra o app, gratuito.
- O conector atual lê a página pública de busca (permitida pelo robots.txt) e grava as ofertas no histórico. Se a Creators API entrar no lugar, as ofertas dela precisam sair do histórico como as do Mercado Livre.
- Passo do dono: entrar no Associados Brasil, chegar a 10 vendas em 30 dias e criar a credencial em Associates Central, Tools, Creators API, Create Application (Credential ID, Secret e versão; OAuth 2.0 com token de uma hora).

### Magazine Luiza

- Programa próprio, o Parceiro Magalu, com comissão de até 12% ([parceiromagalu.com.br](https://www.parceiromagalu.com.br/)). Nenhuma API ou feed de produtos para afiliados encontrado.
- As APIs de [developers.magalu.com](https://developers.magalu.com/) são para vendedores e integradoras: preço e estoque do próprio portfólio, com escopos de seller. Não expõem o catálogo público nem frete por CEP.
- Passo do dono: nenhum que traga dados hoje. A Magalu continua aparecendo pelo Buscapé e como vendedora dentro da Americanas.

### Grupo Casas Bahia (Casas Bahia, Ponto, Extra)

- A página oficial de afiliados respondeu 403 à leitura automatizada, e o perfil do anunciante na Awin só abre com login. Pela busca na web, o programa roda na Awin.
- A Awin documenta feeds de produto para publishers, com comparadores de preço citados como o público principal. As colunas incluem `price`, `product_price_old`, `in_stock`, `stock_quantity`, `delivery_cost`, `delivery_time`, `ean`, `deep_link` e `last_updated`; o frete é um valor fixo, sem CEP ([colunas](https://help.awin.com/developers/docs/hosting-feeds), [feeds](https://help.awin.com/developers/docs/product-feed-publisher-guide-intro.md)).
- `robots.txt`, lido num navegador em 18/11/2026 e igual nas três lojas: libera `*/b` (a busca por caminho, como `/geladeira-frost-free-559l/b`, com os produtos no `__NEXT_DATA__`) e proíbe `*/b?q` e `*/pdp-api`. A Brastemp BRO85 aparece nessa página.
- Sem conector direto: o Akamai Bot Manager responde 403 a todo cliente que não passa no desafio de JavaScript, até no `robots.txt` e com o agente do zpektral. Só um navegador de verdade chega à página, e passar disso seria contornar a proteção.
- Revisto em 19/11/2026: Casas Bahia (anunciante 17629) e Extra (17874) seguem na Awin, com 3% em produtos próprios e 2% de terceiros e cookie de 7 dias; o Extra não aceita pessoa física. Não foi achado perfil próprio do Ponto. O grupo está em recuperação judicial desde 16/08/2026, e o programa pode mudar.
- Feeds da Awin: lista em CSV pela chave de datafeed, Create-a-Feed em CSV com colunas escolhidas, e a API de feed no formato Google em JSONL (5 requisições por minuto, sem exemplo de locale brasileiro) ([lista](https://help.awin.com/developers/docs/downloading-a-list-of-your-product-feeds.md), [API](https://help.awin.com/apidocs/retail-publisher-productapidocumentation-1.md)). A Publisher API não tem busca de produtos. Os termos brasileiros da Awin (agosto de 2025) exigem reproduzir os dados do anunciante com fidelidade (9.2.11) e não tratam de guardar preço.
- Não verificado: se Casas Bahia ou Extra publicam feed e o que os termos de cada anunciante dizem sobre comparadores (só logado).
- Importador não escrito: sem conta, não há como conferir o formato nem se o anunciante permite. Desenho previsto, quando houver feed aprovado: sincronização periódica fora da busca (como a atualização agendada), tabela própria com identidade pelo EAN, oferta que some do feed vira indisponível, validade pela data de importação, ofertas como origem `comparador` e sem frete por CEP.
- Passo do dono: criar conta de publisher na Awin (muitos programas pedem CNPJ), pedir entrada nos programas da Casas Bahia e do Extra e conferir no painel se há feed de produtos e se o anunciante aceita comparador.

### MadeiraMadeira

- `/afiliados` não existe (404) e a página inicial não tem link de afiliados, parceiros ou API. Nada encontrado.

### Leroy Merlin

- A página oficial do programa respondeu 403. Uma notícia de outubro de 2024 ([GiroNews](https://gironews.com/construcao/leroy-merlin-lanca-programa-de-afiliados-para-profissionais/)) diz que o programa usa a Rakuten Advertising, é voltado a profissionais e influenciadores e paga de 3% a mais de 10%.
- Não verificado: feed ou API de produtos. A página de Product Search da Rakuten não carregou o conteúdo.
- Passo do dono: cadastro de publisher na Rakuten Advertising (signup.linkshare.com) e pedido de entrada no programa.

### Shopee (integrada, aguardando acesso)

Documentação lida em 19/11/2026 nos arquivos JavaScript públicos do portal de afiliados brasileiro (a página só carrega com JavaScript) e em cópias de terceiros.

- **Conector conferido:** endpoint `https://open-api.affiliate.shopee.com.br/graphql`, cabeçalho `SHA256 Credential=..., Timestamp=..., Signature=...` com SHA-256 de App ID, instante, corpo e segredo (o exemplo oficial bate), instante com tolerância de 10 minutos. Todos os campos pedidos em `productOfferV2` existem; `priceMin` e `priceMax` são texto e `priceDiscountRate` é inteiro em porcentagem.
- **Preço:** a API dá o preço mínimo e o máximo do anúncio, sem dizer a qual versão cada um pertence, sem preço antigo e sem cupom. Quando o máximo passa do mínimo, a oferta mostra o mínimo com o aviso "Preço da versão mais barata" e o total deixa de contar como exato. A porcentagem de desconto não vira mais preço "de".
- **Erros:** chegam com HTTP 200 em `errors[].extensions.code`. Assinatura recusada (10020), conta sem acesso, congelada ou na lista negra (10031 a 10035) e limite estourado (10030) deixam a fonte `bloqueada`; no 10030 ela fica 15 minutos sem chamar a API. O limite no Brasil é de 2.000 consultas por hora; cada busca usa até `SHOPEE_PAGINAS` (2).
- **Frete:** não há API de frete para afiliados. As ofertas entram sem frete e, no menor total, ficam abaixo das que têm total confirmado. O frete pelo navegador (`SHOPEE_FRETE_NAVEGADOR`) continua desligado e não deve ser ligado em produção: os termos de afiliado proíbem scraping (4.3d) e a página da Shopee tem verificação de robô.
- **Product Feed** (`listItemFeeds` e `getItemFeedData`, desde 05/03/2026): catálogos diários completos e de alterações, até 500 linhas por chamada. Serviria para sincronizar sem gastar a cota, mas as colunas não estão documentadas; fica para depois do acesso.
- **Termos** ([artigo 124094](https://help.shopee.com.br/portal/10/article/124094-Programa-de-Afiliados-Shopee-Termos-e-Condi%C3%A7%C3%B5es), 09/09/2026): o site precisa ser cadastrado e aprovado como mídia; não pode usar marca ou logotipo da Shopee como se fosse dela (2.3a); proibido indexar links de afiliado (4.3k) e redirecionar sozinho para eles (4.4). Os links de oferta do site saem com `nofollow` e só abrem com clique. Risco: o link "Termos" do portal aponta para o artigo 76443, de vendedores, que proíbe links para outras lojas; confirmar com a Shopee qual texto vale para um comparador.
- **Passo do dono:** conta em affiliate.shopee.com.br com o site cadastrado como mídia, pedido de acesso à Open API pelo formulário do painel (sem critério público) e `SHOPEE_ID_APP` e `SHOPEE_SEGREDO` como variáveis sensíveis da API.

### AliExpress

- Não verificado: o portal de afiliados e a documentação da API só carregam com JavaScript, e a página de documentação antiga respondeu 500. Pelo código de um SDK de terceiros, `aliexpress.affiliate.product.query` aceita `ship_to_country`, `target_currency` e `target_language`; resposta em reais e custo de frete não foram confirmados.
- Imposto vigente desde 12/05/2026 (Lei 15.502, de 10/09/2026), para pessoa física no Remessa Conforme: imposto de importação zero até US$ 50 e 60% com desconto de US$ 30 acima disso; fora do programa, 60% sem desconto; ICMS de 17% a 20% calculado por dentro ([Receita Federal](https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/manuais/remessas-postal-e-expressa/preciso-pagar-impostos-nas-compras-internacionais/quanto-pagarei-de-imposto)). O AliExpress entraria pelas regras do Remessa Conforme, diferentes das do eBay.

### eBay (integrado, sem credenciais)

- A estimativa do conector segue a regra de fora do Remessa Conforme (60% sem desconto e ICMS por dentro, 20% por padrão), que continua valendo.
- A Buy API é para parceiros do eBay Partner Network, o frete precisa aparecer separado mesmo quando é grátis, e o limite é de 5.000 chamadas por dia na Browse. Se o cadastro no Partner Network aceita residente no Brasil não foi verificado (a página respondeu 403).


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

1. Mercado Livre: criar o app (escopos `read` e `offline_access`, permissão "Publicação e sincronização"), autorizar a migração `0004` na produção e rodar `scripts.autorizar_mercadolivre --vercel`. Se o catálogo responder 403 mesmo com a permissão, o acesso depende do próprio Mercado Livre.
2. Shopee: cadastrar o site como mídia, pedir acesso à Open API, configurar as duas variáveis e confirmar com a Shopee se os termos de afiliado aceitam um comparador.
3. Amazon: entrar no Associados Brasil e gerar 10 vendas em 30 dias para liberar a Creators API.
4. Casas Bahia e Extra: conta de publisher na Awin (CNPJ), entrada nos programas e conferência do feed e dos termos de cada anunciante.
5. Leroy Merlin: conta de publisher na Rakuten Advertising e entrada no programa.
6. SerpApi ou DataForSEO: só depois de leitura jurídica dos termos, e com orçamento mensal.
