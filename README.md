<p align="center">
  <img src="frontend/src/app/icon.svg" width="56" alt="">
</p>

<h1 align="center">zpektral</h1>

<p align="center">
  Compara o preço final de um produto em dezenas de lojas brasileiras, já com o frete para o seu CEP.
</p>

<p align="center">
  <a href="https://zpektral.vercel.app">Abrir o site</a> ·
  <a href="https://zpektral-api.vercel.app/docs">Documentação da API</a>
</p>

<p align="center">
  <a href="https://github.com/noitsuka/zpektral/actions/workflows/ci.yml"><img src="https://github.com/noitsuka/zpektral/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

![Página inicial](docs/capturas/inicio.png)

## Visão geral

O preço do anúncio quase nunca é o que você paga no fim. O frete muda conforme o CEP, o Pix costuma ter desconto, o parcelamento pode ter juros e algumas lojas somam impostos que só aparecem no fechamento da compra.

O zpektral faz esse caminho em todas as lojas ao mesmo tempo. Você digita o produto e o CEP, o site coloca o item no carrinho de cada loja, lê o valor que seria cobrado na hora de pagar e mostra as lojas lado a lado, da mais barata para a mais cara. Os resultados aparecem enquanto as lojas respondem. Na mediana de 10 buscas medidas sem CEP, a primeira oferta relevante chegou em 0,42 s e a busca inteira terminou em cerca de 7 s.

Para testar, abra o [site](https://zpektral.vercel.app) e procure "geladeira frost free" ou "air fryer" com um CEP qualquer.

## Telas

| Resultado de uma busca | No celular |
| --- | --- |
| ![Resultado de uma busca](docs/capturas/resultado.png) | ![Resultado no celular](docs/capturas/resultado-celular.jpg) |

## Funcionalidades

### Para quem compra

- Preço final de cada loja para o CEP informado, com frete, prazo e transportadora
- Conta aberta de cada oferta: desconto no Pix, frete e o custo dos juros do parcelamento em reais
- Aviso quando a oferta está abaixo ou acima do preço típico do produto entre as lojas
- Histórico do preço na própria loja, com o aviso "menor preço desta loja em N dias" quando for o caso
- Desconto com evidência: o desconto anunciado pela loja aparece como anunciado, a queda em relação ao histórico aparece como verificada, e o preço "de" que nunca foi visto ganha um alerta
- Página de quedas de preço observadas nas buscas, com mediana, menor preço e dias de observação
- Ofertas parecidas ficam separadas das que casam com a busca, com o que falta em cada uma. Se a busca tem marca, outras marcas não aparecem, e "jbl flip 6" não traz a JBL Charge 6
- Cada palavra da busca é um pedido, e a coleira para gatos não aparece em "coleira antipulgas cachorro". Quando quase nenhuma loja tem o produto exato, a busca se reavalia com a palavra rara pesando mais que a comum, pela frequência em 79 mil títulos reais: "mangá punpun" traz os volumes de Boa Noite Punpun, que não repetem "mangá", e não traz camiseta de manga curta; "oyasumi punpun" acha a edição brasileira. Palavra que nenhuma loja usa, como "bonita" em "air fryer bonita", e palavra de intenção, como "barata", deixam de esconder as ofertas
- "sem fio" não traz fone com fio, e o ano pedido ("camisa do corinthians 2024") que o anúncio não repete não esconde o produto, mas outro ano esconde
- Busca que entende nomes diferentes para o mesmo produto, como "máquina de lavar louça" e "lava-louças", corrige erros de digitação e acentos esquecidos, como "geladiera" e "fogao", e aceita o código de barras (EAN) do produto
- Separação entre o produto e as peças dele: o cesto da air fryer não aparece como air fryer, e produtos de marcas ou EANs diferentes não se misturam
- Filtros por voltagem, condição e forma de pagamento
- Buscas recentes guardadas só no navegador

### Por baixo

- O total exato vem do carrinho da loja, sem estimativa; o que a loja não informa aparece como não informado
- Parte das cotações é refeita em paralelo, e o vendedor que devolve valores diferentes para o mesmo carrinho perde o selo de total exato
- Nenhum bloqueio das lojas contra robôs é contornado, e a loja que passa a proibir o acesso no robots.txt sai da lista (`pytest -m live` confere)
- O histórico guarda a busca simplificada (nunca com e-mail ou números longos, como CPF) e só os cinco primeiros dígitos do CEP; o texto da busca some em 14 dias e o resto em 180
- As buscas mais feitas são refeitas a cada 6 horas para manter o histórico em dia

## Lojas

95 lojas da plataforma VTEX (Carrefour, Americanas, Atacadão, WebContinental, Quero-Quero, KitchenAid, Drogaria São Paulo, Levi's, Vivara, H.Stern e outras de eletro, casa, construção, moda, calçados, esporte, beleza, farmácia, mercado, joias e ótica), mais Amazon, KaBuM! e Buscapé. Mercado Livre, Shopee e eBay estão integrados pelas APIs oficiais e entram quando as credenciais são configuradas. A lista completa, o estado medido de cada fonte e a pesquisa de novas fontes oficiais estão em [docs/fontes.md](docs/fontes.md).

O frete é cotado no carrinho das lojas VTEX e dos vendedores dentro delas. Amazon, KaBuM! e Buscapé entram com o preço e o frete que mostram publicamente. Produtos do eBay vindos do exterior aparecem com o imposto de importação estimado e uma marca própria. A loja que recusa o acesso (HTTP 401, 403, 429 ou verificação de robô) aparece como bloqueada, separada da loja fora do ar.

## Stack

| Camada | Tecnologias |
| --- | --- |
| Backend | Python 3.14, FastAPI, httpx, SQLAlchemy 2 (async), Pydantic 2, Alembic |
| Banco | PostgreSQL 17 em produção, SQLite no desenvolvimento |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Qualidade | pytest, Hypothesis, Vitest, Ruff, Pyright, ESLint, Prettier, Knip, GitHub Actions |
| Infra | Docker, Vercel, Neon |

## Arquitetura

```mermaid
flowchart LR
    pessoa([Pessoa]) --> site[Next.js]
    site -->|SSE| api[FastAPI]
    api --> lojas[Lojas VTEX, Amazon, KaBuM!, Buscapé]
    lojas -->|carrinho com o CEP| api
    api --> banco[(PostgreSQL)]
```

Cada busca vira um trabalho único por consulta e CEP: quem pede a mesma coisa ao mesmo tempo espera o mesmo trabalho, e o resultado fica em cache por cinco minutos. As lojas respondem em paralelo e cada uma entra na tela assim que termina.

```
backend/app/
  fontes/         um adaptador por loja, todos com a mesma interface
  busca.py        execução em paralelo, cache e limpeza dos dados das lojas
  relevancia.py   nota de cada título contra a busca, sinônimos, erros de digitação, peças
  agrupamento.py  mesmo produto em lojas diferentes, por EAN e código de modelo
  historico.py    histórico de preços por oferta
  limites.py      limites por endereço e cabeçalhos de segurança
frontend/src/
  app/            página inicial, resultados, quedas de preço e privacidade
  componentes/    menor total, linhas por loja, filtros, histórico
  nucleo/         filtros, juros, tendência e promoções com evidência (funções puras)
docs/decisoes/    registro das decisões
```

## Decisões técnicas

1. [O carrinho da loja é a fonte da verdade](docs/decisoes/01-checkout-como-fonte-da-verdade.md). Só o valor lido no carrinho recebe o selo de total exato.
2. [Só fontes abertas ou oficiais](docs/decisoes/02-fontes-abertas-ou-oficiais.md). Páginas públicas permitidas pelo `robots.txt` ou APIs oficiais.
3. [Mesmo produto em lojas diferentes](docs/decisoes/03-identidade-do-produto.md). Agrupado por EAN e código de modelo, nunca só pelo título.
4. [Um processo, com estado em memória](docs/decisoes/04-um-processo-com-estado-em-memoria.md). Cache e limites sem Redis, até o volume pedir.
5. [Conferência das cotações](docs/decisoes/05-auditoria-de-cotacoes.md). Cotações repetidas em paralelo para achar preços instáveis.
6. [Importados com total estimado](docs/decisoes/06-importados-com-total-estimado.md). Imposto de importação e ICMS calculados à parte e marcados.
7. [Símbolo em forma de prisma](docs/decisoes/07-simbolo-prisma.md). O Z separa o preço anunciado nas linhas de cada loja.
8. [Histórico de preço na própria loja](docs/decisoes/08-historico-por-oferta.md). O preço de hoje comparado com o habitual daquela loja.
9. [Atualização agendada de preços](docs/decisoes/09-atualizacao-agendada-de-precos.md). GitHub Actions a cada 6 horas, porque o cron gratuito da Vercel roda uma vez por dia.

## Segurança

| Cenário | Resposta |
| --- | --- |
| Muitas buscas novas do mesmo endereço | `429`, com limite bem menor que o de leituras do cache |
| `X-Forwarded-For` forjado ou troca de IPv6 dentro do mesmo /64 | o limite continua valendo |
| Loja que redireciona para um endereço interno | requisição recusada, só hosts públicos e `https` |
| Resposta gigante de uma loja | cortada no teto de tamanho |
| HTML ou caracteres de controle num título | removidos antes de chegar ao site |
| Erro inesperado | `500` com mensagem genérica e código de correlação |

Credenciais ficam só em variáveis de ambiente e nunca aparecem nos logs. O site envia uma Content-Security-Policy que só carrega scripts da própria origem ou inline e só abre conexões com a própria origem e com a API.

## Testes

```bash
cd backend
pip install -e ".[dev]"
pytest
```

Pouco mais de 1.100 testes, com respostas reais das lojas gravadas, testes de propriedades e 300 entradas aleatórias contra a API. A suíte `pytest -m live` busca cinco produtos em cinco capitais, sorteia ofertas e refaz o carrinho na loja para conferir o total; na última execução, 300 ofertas conferidas e nenhuma divergência. No frontend, `npm test`, `npm run lint` e `npx knip`. `npm run e2e` roda onze cenários ponta a ponta com Playwright, no desktop e no celular, com o build de produção e uma API falsa que serve dados gerados pelo próprio backend (`backend/scripts/dados_e2e.py`); a CI roda todos eles.

## Executando localmente

Requisitos: Docker, ou Python 3.12+ e Node.js 24.

```bash
docker compose up --build
```

Site em `http://localhost:3000` e API em `http://localhost:8000` (documentação em `/docs`). Sem Docker, a API sobe com `uvicorn app.main:app` dentro de `backend` e o site com `npm run dev` dentro de `frontend`. Sem banco configurado, o histórico vai para um arquivo SQLite local. O passo a passo sem Docker, com PostgreSQL portátil no Windows, está em [docs/desenvolvimento.md](docs/desenvolvimento.md).

## Deploy

Site e API são dois projetos na Vercel, e o banco é um PostgreSQL no Neon conectado pela integração da Vercel. A API roda na região de São Paulo ([`backend/vercel.json`](backend/vercel.json)): saindo dos Estados Unidos, a mesma busca perdia 13 lojas. O passo a passo para publicar uma versão nova, com migração e volta atrás, está em [docs/implantacao.md](docs/implantacao.md), e a homologação isolada da produção em [docs/homologacao.md](docs/homologacao.md).

| Variável | Onde | Descrição |
| --- | --- | --- |
| `DATABASE_URL_UNPOOLED` | API | conexão direta ao PostgreSQL (preenchida pela integração) |
| `ORIGENS_CORS` | API | lista JSON com a origem do site |
| `CONFIAR_PROXY` | API | `true` atrás do proxy da Vercel |
| `HSTS` | API | `true` em produção |
| `ML_ID_CLIENTE`, `SHOPEE_ID_APP`, `EBAY_ID_CLIENTE` e segredos | API | opcionais, ativam Mercado Livre, Shopee e eBay |
| `NEXT_PUBLIC_URL_API` | Site | URL pública da API |
| `NEXT_PUBLIC_URL_SITE` | Site | URL pública do site, usada no compartilhamento |

Migrações: `alembic upgrade head` dentro de `backend`, com a URL direta do banco em `DATABASE_URL` e sem `DATABASE_URL_UNPOOLED` no ambiente, porque ela tem prioridade. O roteiro com as conferências está em [docs/implantacao.md](docs/implantacao.md).

## Limitações e próximos passos

- Magazine Luiza, Casas Bahia e outras lojas que bloqueiam acesso automatizado aparecem só pelo Buscapé, com preço e sem frete.
- Leroy Merlin, MadeiraMadeira, Tok&Stok e Mobly não têm API pública que dê para usar ou proíbem o acesso no robots.txt. Riachuelo, Farm, Animale, Avon, Havaianas, Pandora e outras lojas VTEX ficam de fora pelo mesmo motivo.
- Redes regionais, como Savegnago, Giassi, GBarbosa e Drogasmil, só cotam frete para CEPs da própria região e aparecem como "não entrega" nos outros.
- KaBuM! e Amazon entram sem cotação de frete por CEP. A Creators API, que substituiu a PA-API da Amazon, também não traz frete e exige conta de Associados com vendas.
- O total de produtos do eBay é estimado, porque o imposto final é definido pela Receita na chegada.
- Próximo passo: feeds de afiliados (Awin para Casas Bahia, Rakuten Advertising para Leroy Merlin), que dependem de conta do dono, e Redis para rodar mais de um processo.

## Licença

[MIT](LICENSE)
