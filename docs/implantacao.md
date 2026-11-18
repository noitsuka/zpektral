# Como publicar a versão nova

A versão nova depende da migração `0003` no Neon. A migração só acrescenta colunas (`preco_original`, `link`, `imagem` e `consulta`, que aceitam vazio, e `agendada`, com valor padrão `false`), então o código que está no ar continua funcionando com o banco já migrado. Por isso a ordem é: banco, API e, por último, o site.

Nenhuma variável de ambiente nova é obrigatória.

## 1. Antes de tudo

1. Conferir que a CI passou no commit que vai ao ar (API, site, testes ponta a ponta e imagens).
2. No Neon, criar um branch do banco de produção como ponto de restauração, com nome como `antes-0003`. É instantâneo e não copia dados de fato.
3. Rodar a migração primeiro nesse branch, com a URL direta dele (não a do pooler):

Antes de cada `alembic upgrade` deste documento, conferir o alvo como em `docs/homologacao.md`, passo 1: `DATABASE_URL_UNPOOLED` tem prioridade sobre `DATABASE_URL`, e um valor esquecido na sessão migraria outro banco.

```powershell
cd backend
Remove-Item Env:DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
$env:DATABASE_URL = "<url direta do branch antes-0003>"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
```

`alembic check` precisa dizer `No new upgrade operations detected`.

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
2. Uma busca com CEP no site mostra a etiqueta do menor total e as lojas que responderam.
3. Uma busca com CEP de outra região (por exemplo `69900-000`) mostra "Nenhuma loja entrega no CEP" quando for o caso.
4. `GET /ofertas/quedas` responde 200. A lista fica vazia até o histórico ter 5 dias de observações por oferta.
5. Depois de uma busca, `select count(*) from historico_precos where consulta is not null` cresce.

## 5. Se der errado

- Site ou API: na Vercel, "Instant Rollback" para o deploy anterior de cada projeto. O banco migrado continua compatível com o código antigo.
- Banco: só se for preciso desfazer a coluna nova, `alembic downgrade 0002`. Isso apaga apenas os dados das colunas acrescentadas. Para voltar tudo, restaurar a partir do branch `antes-0003`.

## 6. Atualização agendada (opcional)

O workflow `atualizar-precos` só roda quando o secret `DATABASE_URL` existe no GitHub. Ele não deve receber o dono do banco: crie um papel só com o que o script usa.

```sql
create role zpektral_atualizador login password '<senha forte>';
grant connect on database <nome do banco> to zpektral_atualizador;
grant usage on schema public to zpektral_atualizador;
grant select, insert, update, delete on historico_precos, saude_lojas to zpektral_atualizador;
grant usage, select on all sequences in schema public to zpektral_atualizador;
```

Depois, coloque no secret a URL direta com esse papel. Limitações conhecidas: os executores do GitHub ficam fora do Brasil, e algumas lojas recusam acesso de fora; o GitHub desliga workflows agendados depois de 60 dias sem commits no repositório.
