# Só fontes abertas ou oficiais

Aceita em outubro de 2026.

## Contexto

Mercado Livre, Amazon, Magazine Luiza, Casas Bahia e outras lojas grandes bloqueiam acesso automatizado com Cloudflare e Akamai. Existem técnicas para passar por esses bloqueios, como imitar a assinatura TLS de um navegador ou rodar o tráfego por proxies residenciais.

## Decisão

A API não contorna proteções anti-bot e se identifica com um user agent próprio. A cobertura vem de:

- APIs públicas das lojas (catálogo e simulação de checkout VTEX, catálogo da KaBuM!);
- marketplaces que revendem outras lojas (a Americanas tem a Magazine Luiza como vendedora, com frete calculado);
- APIs oficiais com credencial (Mercado Livre e afiliados da Shopee), ativadas pelo `.env`;
- páginas públicas permitidas pelo `robots.txt` da loja, lidas uma vez por busca, sem tentar de novo quando a loja responde com verificação (a busca da Amazon, `/s?k=`, desde outubro de 2026);
- o Buscapé como comparador, que alcança Amazon, Magalu e outras, marcado como origem `comparador` e nunca como total exato.

## Alternativas rejeitadas

- Imitar navegador (TLS, JA3/JA4) e proxies residenciais: viola os termos das lojas, quebra a cada atualização do bloqueio e transforma o projeto em ferramenta de evasão.
- Navegador headless por loja: o mesmo problema, com um custo de memória que inviabiliza 30 fontes em paralelo.

## Consequências

Algumas lojas grandes aparecem com o menor preço do comparador e sem frete calculado, e isso fica explícito na resposta. Em troca, nenhuma fonte para de funcionar quando a loja atualiza o bloqueio.

A Amazon substituiu a PA-API 5.0 pela Creators API, que exige conta de associado aprovada. Até essa credencial existir, a Amazon entra pela busca pública: preço, preço de tabela, parcelamento e imagem saem do HTML; o frete fica sem cotação, porque o CEP só muda a entrega depois de gravado na sessão da loja.

O frete por CEP da Amazon e da Shopee tem um provedor de navegador opcional (`app/navegador`), desligado por padrão (`AMAZON_FRETE_NAVEGADOR`, `SHOPEE_FRETE_NAVEGADOR`). Ele só faz o que um comprador faria: abre a página do produto, informa o CEP, confirma e lê frete e prazo. Usa o Chromium do Playwright com a identidade padrão, sem stealth, sem trocar fingerprint e sem resolver captcha. Verificação de robô vira `automation_challenge`, pedido de login vira `login_required`, e a cotação daquela loja para ali. Os seletores ficam num só lugar por loja, com alternativas por id, aria-label, papel, placeholder e texto.
