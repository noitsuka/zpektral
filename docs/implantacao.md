# Como publicar a versão nova

A versão nova depende da migração `0003` no Neon. A migração só acrescenta colunas (`preco_original`, `link`, `imagem` e `consulta`, que aceitam vazio, e `agendada`, com valor padrão `false`), então o código que está no ar continua funcionando com o banco já migrado. Por isso a ordem é: banco, API e, por último, o site.

Nenhuma variável de ambiente nova é obrigatória.

Antes de cada `alembic upgrade` deste documento, conferir o alvo como em `docs/homologacao.md`, passo 1: `DATABASE_URL_UNPOOLED` tem prioridade sobre `DATABASE_URL`, e um valor esquecido na sessão do terminal migraria outro banco.

## 1. Antes de tudo

1. Conferir que a CI passou no commit que vai ao ar (API, site, testes ponta a ponta e imagens).
2. No Neon, criar um branch do banco de produção como ponto de restauração, com nome como `antes-0003`, e não mexer nele. É instantâneo e não copia dados de fato.
3. Criar outro branch da produção para o ensaio, como `ensaio-0003`, e rodar a migração primeiro nele, com a URL direta dele (não a do pooler). Migrar o próprio `antes-0003` estragaria o ponto de restauração:

```powershell
cd backend
Remove-Item Env:DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
$env:DATABASE_URL = "<url direta do branch ensaio-0003>"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
```

`alembic check` precisa dizer `No new upgrade operations detected`. Depois do ensaio, o `ensaio-0003` pode ser apagado.

## 2. Banco de produção

Com a URL direta de produção (`DATABASE_URL_UNPOOLED` na Vercel):

```powershell
Remove-Item Env:DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
$env:DATABASE_URL = "<url direta de produção>"
.venv\Scripts\python.exe -m alembic upgrade head
```

Conferir em SQL: `select version_num from alembic_version` deve devolver `0003`.

## 3. API e site

Os deploys saem da pasta de cada projeto, pela CLI da Vercel:

```powershell
cd backend
npx vercel@latest --prod
cd ..\frontend
npx vercel@latest --prod
```

A API vai primeiro: o site novo manda `apenas_disponiveis=false` na transmissão e o `cep` no histórico por oferta, e a API antiga ignoraria o segundo.

## 4. Conferência depois do deploy

1. `GET https://zpektral-api.vercel.app/saude` responde 200.
2. Uma busca com CEP no site mostra o menor total no CEP na primeira linha e quantas lojas responderam.
3. Uma busca com CEP de outra região (por exemplo `69900-001`, em Rio Branco) mostra "Nenhuma loja entrega no CEP" quando for o caso.
4. `GET /ofertas/quedas` responde 200. A lista fica vazia até o histórico ter 5 dias de observações por oferta.
5. Depois de uma busca, `select count(*) from historico_precos where consulta is not null` cresce.

## 5. Se der errado

- Site ou API: na Vercel, "Instant Rollback" para o deploy anterior de cada projeto. O banco migrado continua compatível com o código antigo.
- Banco: só se for preciso desfazer as colunas novas, `alembic downgrade 0002`. Isso apaga apenas os dados das colunas acrescentadas. Para voltar tudo, restaurar a partir do branch `antes-0003`.

## 6. Atualização agendada (opcional)

O workflow `atualizar-precos` só roda quando o secret `DATABASE_URL` existe no GitHub. Ele não deve receber o dono do banco: crie um papel só com o que o script usa.

```sql
create role zpektral_atualizador login password '<senha forte>';
grant connect on database <nome do banco> to zpektral_atualizador;
grant usage on schema public to zpektral_atualizador;
grant select, insert, update, delete on historico_precos, saude_lojas to zpektral_atualizador;
grant usage, select on all sequences in schema public to zpektral_atualizador;
```

Depois, coloque no secret a URL direta com esse papel. Limitações conhecidas: os executores do GitHub ficam fora do Brasil, e algumas lojas recusam acesso de fora; o GitHub desliga workflows agendados depois de 60 dias sem atividade no repositório público.

## 7. Mercado Livre (migração 0004 e credenciais)

Antes de qualquer passo: os termos da API do Mercado Livre não autorizam, do jeito que estão escritos, o uso num comparador que mistura as ofertas dele com as de outras lojas (`docs/fontes.md`, seção Mercado Livre). Ativar depende de autorização escrita do Mercado Livre.

A migração `0004` só cria a tabela `credenciais_oauth`, então o código no ar continua funcionando com ela. Ordem, primeiro na homologação e só depois na produção:

1. Ponto de restauração e ensaio como nas seções 1 e 2, com os nomes `antes-0004` e `ensaio-0004`; `select version_num from alembic_version` deve devolver `0004`. Na homologação, a migração vai no branch `homologacao` do Neon (`docs/homologacao.md`, passo 1), que é uma cópia isolada: o `main` não muda.
2. Não dar ao papel `zpektral_atualizador` nenhum acesso a `credenciais_oauth`: a atualização agendada não usa o Mercado Livre.
3. Autorizar com `python -m scripts.autorizar_mercadolivre --vercel preview` (homologação) ou `--vercel production` (produção, pede para digitar `producao` antes de qualquer contato com o Mercado Livre). Cada execução é uma autorização nova, com chave nova, gravada como sensível só no ambiente escolhido de `zpektral-api`. Use um app do Mercado Livre para cada ambiente: a documentação diz que só vale o último refresh token gerado, e não diz se uma autorização nova derruba a anterior do mesmo app.
4. Deploy da API no mesmo ambiente e uma busca de conferência. Na primeira, a fonte renova o token e grava a linha cifrada.

Na Vercel, a fonte só liga com o cofre num PostgreSQL: sem `DATABASE_URL`, ela fica desligada e o log diz o motivo.

Quando é preciso autorizar de novo (a fonte aparece como `bloqueada`, com o comando no motivo):

- restaurar o banco a partir de um branch anterior à última renovação, porque ele traz um refresh token já trocado;
- trocar a `CHAVE_CREDENCIAIS`, porque a linha deixa de abrir. A fonte não reapresenta a semente;
- perder a resposta da renovação depois de o Mercado Livre trocar o token, ou a instância morrer entre a troca e a gravação. O código não tem como evitar esses dois.

Não fazer "Redeploy" na Vercel de um build anterior a esta versão com as variáveis do Mercado Livre no ambiente: o código antigo não conhece o cofre e apresentaria a semente.
