# Homologação isolada da produção

## Estado conferido em 18/11/2026

- **Git:** a `main` local está à frente de `origin/main` (`195fc21`), e a `release/homologacao` ainda não foi publicada. Nada foi enviado ao GitHub.
- **GitHub:**
  - o repositório é público, sem secrets, variáveis ou environments;
  - o token padrão dos workflows só lê;
  - no remoto só existe o workflow `ci`. O `atualizar-precos` passa a existir no primeiro push da `main` e fica parado enquanto não houver o secret `DATABASE_URL`.
- **CI:** roda em push na `main` e na `release/homologacao` e em pull requests. Migra só o Postgres do próprio executor, e o job `imagens` só constrói as imagens, sem publicar. Nenhum push publica nem migra nada fora da CI.
- **Vercel:**
  - `zpektral` e `zpektral-api` não estão ligados ao Git ("Git Repository: Not connected"), então um push não gera deploy;
  - na API, as 18 variáveis da integração do Neon (`DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `PG*`, `POSTGRES_*`, `NEON_*`, `VITE_NEON_AUTH_URL`) valem para Production, **Preview** e **Development**, e `ORIGENS_CORS`, `CONFIAR_PROXY` e `HSTS` só para Production;
  - no site, `NEXT_PUBLIC_URL_API` e `NEXT_PUBLIC_URL_SITE` só valem para Production;
  - a Deployment Protection (Vercel Authentication) está ligada nos dois projetos: a URL própria de cada deploy redireciona para o login da Vercel, e só `zpektral.vercel.app` e `zpektral-api.vercel.app` são públicos.
- **API:** nunca altera o esquema do Postgres ao subir (só cria tabelas quando o banco é SQLite). Migração só acontece por `alembic`, rodado à mão.
- **Migração `0003`:** ensaiada no Postgres 17.12 local, sobre 200 mil linhas na `0002`:
  - executa só cinco `ALTER TABLE historico_precos ADD COLUMN`, sem reescrever a tabela;
  - contagem e soma dos totais ficaram iguais antes e depois, e `agendada` ficou falsa em todas as linhas;
  - `alembic check` saiu limpo;
  - `downgrade 0002` e um novo `upgrade head` também não perderam linhas.

Para ver o SQL exato sem conectar em nada, dentro de `backend`: `.venv\Scripts\python.exe -m alembic upgrade 0002:0003 --sql`.

## O que impede a homologação hoje

1. Um deploy de preview da API usaria o banco de produção, que ainda está na `0002`, com código que grava colunas da `0003`.
2. Com a Vercel Authentication ligada na API, o navegador recebe o redirecionamento para o login em vez da resposta, e a busca do site de preview falha.
3. A URL de um preview muda a cada deploy. Sem nomes fixos, o CORS da API e a `NEXT_PUBLIC_URL_API` do site viram um ciclo: mudar uma variável pede um deploy novo, que gera outra URL.
4. `ORIGENS_CORS`, `CONFIAR_PROXY` e as `NEXT_PUBLIC_URL_*` não existem em Preview.

Os passos 1 a 3 resolvem os quatro. Todos dependem do dono: são mudanças no Neon e na Vercel.

## Ambientes

| Ambiente | Banco | API | Site |
|---|---|---|---|
| Desenvolvimento | PostgreSQL local (`docs/desenvolvimento.md`) ou SQLite | `uvicorn` local | `npm run dev` |
| Homologação | branch `homologacao` do Neon | `zpektral-api-homologacao.vercel.app` (preview) | `zpektral-homologacao.vercel.app` (preview) |
| Produção | branch principal do Neon | `zpektral-api.vercel.app` | `zpektral.vercel.app` |

Se algum dos dois nomes já estiver ocupado na hora do passo 3, escolha outro e use o mesmo nos passos 2 e 3.

## 1. Banco de homologação (Neon)

1. No Neon, criar o branch `homologacao` a partir do principal.
2. Copiar a URL **direta** do branch, a que não tem `-pooler` no host.
3. Conferir o alvo antes de migrar. A configuração dá prioridade a `DATABASE_URL_UNPOOLED` sobre `DATABASE_URL`: um valor esquecido na sessão do PowerShell migraria outro banco sem aviso.

```powershell
cd backend
Remove-Item Env:DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
$env:DATABASE_URL = "<url direta do branch homologacao>"
.venv\Scripts\python.exe -c "from app.configuracao import obter_configuracoes as c; from sqlalchemy.engine import make_url as m; u = m(c().url_banco); print('alvo:', u.host, u.database)"
```

O host impresso (`ep-...`) precisa ser o do branch `homologacao` no console do Neon. Cada branch tem um endpoint próprio. Só então:

```powershell
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
Remove-Item Env:DATABASE_URL
```

`current` deve mostrar `0002` antes e `0003` depois, e `check` deve dizer `No new upgrade operations detected.`

## 2. Vercel: variáveis e proteção (painel)

**`zpektral-api`, Settings > Environment Variables:**

- Tirar **Preview** e **Development** de todas as variáveis da integração do Neon. Elas são gerenciadas pela integração, então, se o painel não deixar editar, mude os ambientes na conexão do banco, em Storage.
- Criar só para **Preview**:
  - `DATABASE_URL` com a URL do branch `homologacao` (com pooler);
  - `DATABASE_URL_UNPOOLED` com a URL direta do mesmo branch;
  - `ORIGENS_CORS` igual a `["https://zpektral-homologacao.vercel.app"]`;
  - `CONFIAR_PROXY` igual a `true`.
- Development fica sem banco: o desenvolvimento usa o Postgres local.

**`zpektral`, Settings > Environment Variables, só para Preview:**

- `NEXT_PUBLIC_URL_API` igual a `https://zpektral-api-homologacao.vercel.app`;
- `NEXT_PUBLIC_URL_SITE` igual a `https://zpektral-homologacao.vercel.app`.

**Deployment Protection:**

- Em `zpektral-api`, desligar a Vercel Authentication durante a homologação. A API de produção já é pública, então nada novo fica exposto.
- No site, a proteção pode continuar ligada para teste manual: você entra com a conta da Vercel. Para o smoke automático (passo 4), ela precisa estar desligada também.
- Religar as duas ao fim da homologação.

## 3. Publicar em preview com nomes fixos

Os nomes fixos quebram o ciclo do item 3: o CORS e as URLs já apontam para eles antes de qualquer deploy.

```powershell
git switch release/homologacao
cd backend
npx vercel@latest
npx vercel@latest alias set <url do preview da API> zpektral-api-homologacao.vercel.app
cd ..\frontend
npx vercel@latest
npx vercel@latest alias set <url do preview do site> zpektral-homologacao.vercel.app
```

- Sem `--prod`, o comando cria um deploy de preview e mostra a URL.
- Este checkout não está ligado a nenhum projeto, então a CLI vai perguntar qual usar. Escolha o projeto existente (`zpektral-api` na pasta `backend`, `zpektral` na pasta `frontend`).
- Se a CLI oferecer ligar o repositório Git, **responda não**: com o Git ligado, cada push passaria a publicar.
- A pasta `.vercel/` que a CLI cria já está no `.gitignore`.
- Depois, `npx vercel@latest project inspect zpektral-api` e `npx vercel@latest project inspect zpektral` devem continuar com `Git Repository: Not connected`.

Para republicar a API ou o site, repita o deploy e o `alias set` daquele projeto. As variáveis não mudam.

## 4. O que conferir em homologação

1. `https://zpektral-api-homologacao.vercel.app/saude` responde 200.
2. Smoke com lojas reais contra o preview:

```powershell
cd frontend
$env:SITE_REMOTO = "https://zpektral-homologacao.vercel.app"
npx playwright test -c playwright.real.config.ts
Remove-Item Env:SITE_REMOTO
```

   Espera-se 8 testes passando (4 no desktop e 4 no celular). Um deles mede o CLS de uma busca ao vivo e exige menos de 0,1. Com `SITE_REMOTO`, a suíte não sobe servidor local. Esse caminho foi validado em 18/11/2026 contra servidores locais subidos à parte.

3. Busca com CEP de outra região (por exemplo `69900-001`, em Rio Branco; o `69900-000` não existe para o serviço de CEP e cai no erro de CEP): quando ninguém entrega, a tela diz "Nenhuma loja entrega no CEP".
4. `GET https://zpektral-api-homologacao.vercel.app/ofertas/quedas` responde 200 (lista vazia é esperada no começo).
5. No branch `homologacao`, `select count(*) from historico_precos where consulta is not null` cresce depois das buscas, e nenhum texto tem e-mail ou sequência longa de números. Como a produção ainda está na `0002`, ela não tem a coluna `consulta`. Se o preview estivesse ligado nela, as gravações dariam erro, visível em `npx vercel@latest logs <url do preview da API>`.

## 5. Checklist da publicação controlada

Já pronto em 18/11/2026:

- [x] `release/homologacao` alinhada com a `main` por fast-forward.
- [x] Backend: 1.068 testes passam e 4 são pulados, contra o Postgres 17.12 local; ruff limpo.
- [x] Frontend: lint, tipos, testes, knip e build limpos. E2E simulado: 20 passam e 2 são pulados de propósito.
- [x] Smoke real: 6 de 6, pelo caminho `SITE_REMOTO`.
- [x] Migração `0003` ensaiada com subida, descida e nova subida, sem perda de linhas.
- [x] CI e workflows conferidos: nenhum push publica nem migra fora da CI.

Depende do dono, nesta ordem:

- [ ] Autorizar o push de `main` e `release/homologacao` e conferir a CI verde nos dois.
- [ ] Passo 1: branch `homologacao` no Neon e `0003` nele, com a conferência do alvo.
- [ ] Passo 2: variáveis de Preview e Development na Vercel e proteção da API desligada.
- [ ] Passo 3: deploys de preview e aliases, com o Git ainda desligado nos dois projetos.
- [ ] Passo 4: as cinco conferências.
- [ ] Religar a Deployment Protection.
- [ ] Produção: `docs/implantacao.md`.
