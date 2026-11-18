# Atualização agendada de preços pelo GitHub Actions

Aceita em novembro de 2026.

## Contexto

O histórico só ganha pontos quando alguém busca. Para dizer que um preço caiu (`GET /ofertas/quedas`), cada oferta precisa de pelo menos 5 dias observados no mês e de uma leitura nas últimas 48 horas, o que as buscas espontâneas não garantem. A API roda em funções da Vercel, sem processo contínuo, e cada busca abre dezenas de lojas por alguns segundos.

## Decisão

O workflow `.github/workflows/atualizar-precos.yml` roda `backend/scripts/atualizar_precos.py` a cada 6 horas (no minuto 17, fora do pico do início da hora) e também sob demanda. O job só começa se o secret `DATABASE_URL` existir no repositório.

O script:

- lê no histórico as buscas feitas por pessoas nos últimos 7 dias; cada busca grava suas linhas com o texto buscado no mesmo instante, e as linhas do próprio script são marcadas como agendadas para não contarem como procura;
- dá a cada busca uma validade de 48 horas dividida por `buscas × (1 + volatilidade)`, entre 5 e 48 horas, sendo a volatilidade a fração das ofertas que mudaram de preço na semana;
- refaz sem CEP as buscas vencidas, da mais procurada e volátil para a menos, até o orçamento da execução (20 por padrão);
- não regrava no mesmo dia o preço que já está no banco.

As linhas agendadas são sem CEP. A rota de quedas usa só a série sem CEP de cada oferta, e o resumo que o site usa ao lado do preço ignora as agendadas: com CEP, uma loja com preço regional ou imposto do destino criaria quedas que não existem.

## Por que não Vercel Cron

- No plano Hobby, o cron roda no máximo uma vez por dia, com até 59 minutos de atraso; a cada 6 horas exige o Pro.
- Uma função no Hobby tem no máximo 300 segundos. Cada busca espera até 12 segundos pelas lojas, mais a gravação, e 20 delas seguidas passam disso no pior caso.
- Uma rota para o cron chamar teria de ficar pública e protegida por segredo na própria API.

No GitHub Actions os executores padrão são gratuitos em repositório público (num privado, entram na cota mensal do plano), o job pode levar até 30 minutos e a conexão com o banco fica num secret.

## Limites

- Os executores do GitHub rodam fora do Brasil. Lojas que recusam acesso de fora (saindo dos Estados Unidos, a busca perdia 13 lojas) ficam sem atualização agendada e só entram pelo histórico das buscas das pessoas.
- O agendamento do GitHub pode atrasar em horários de pico e é desligado depois de 60 dias sem atividade no repositório público.
- Cada execução grava uma linha por oferta relevante e com preço novo no dia. O orçamento é o controle de volume e de carga nas lojas; a retenção de `DIAS_HISTORICO` continua valendo.
- O banco precisa estar na migração `0003` antes de o workflow ou a nova versão da API rodarem.

## Consequências

O histórico passa a guardar o texto da busca que gerou cada linha, sem nada que identifique quem buscou. O log do workflow mostra só quantas buscas foram refeitas, nunca o texto delas.
