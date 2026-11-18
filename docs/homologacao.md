# Homologação isolada da produção

## Estado conferido em 18/11/2026

- Nenhum dos dois projetos da Vercel (`zpektral` e `zpektral-api`) está ligado a um repositório Git. Um push no GitHub não publica nada: roda só a CI, e o workflow `atualizar-precos` fica parado enquanto o secret `DATABASE_URL` não existir.
- Na API, `DATABASE_URL` e `DATABASE_URL_UNPOOLED` (da integração com o Neon) valem para production, **preview** e development. Um deploy de preview hoje usaria o banco de produção.
- `ORIGENS_CORS` (API) e `NEXT_PUBLIC_URL_API` (site) só existem em production. Um preview hoje não conseguiria falar com a API.

Por isso, a homologação só começa depois do passo 1.

## Ambientes

| Ambiente | Banco | API | Site |
|---|---|---|---|
| Desenvolvimento | PostgreSQL local (`docs/desenvolvimento.md`) ou SQLite | `uvicorn` local | `npm run dev` |
| Homologação | branch `homologacao` do Neon | deploy de preview de `zpektral-api` | deploy de preview de `zpektral` |
| Produção | branch principal do Neon | `zpektral-api.vercel.app` | `zpektral.vercel.app` |

## 1. Separar o banco de preview (uma vez)

1. No Neon, criar o branch `homologacao` a partir do principal.
2. Rodar a migração nele, com a URL direta do branch:

```powershell
cd backend
$env:DATABASE_URL = "<url direta do branch homologacao>"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
```

3. Na Vercel, em `zpektral-api` > Settings > Environment Variables, tirar o ambiente **Preview** de `DATABASE_URL` e `DATABASE_URL_UNPOOLED` (e das outras variáveis `PG*` e `POSTGRES_*` da integração) e criar `DATABASE_URL` e `DATABASE_URL_UNPOOLED` só para **Preview**, com as URLs do branch `homologacao`. Uma alternativa é ligar na integração do Neon a criação automática de branch por deploy de preview, se o plano permitir.

## 2. Publicar em preview

```powershell
git switch release/homologacao
cd backend
npx vercel@latest
```

O comando sem `--prod` cria um deploy de preview e mostra a URL. Depois, em Preview:

- `zpektral-api`: `ORIGENS_CORS` com a URL do preview do site (`["https://<preview-do-site>.vercel.app"]`), `CONFIAR_PROXY=true`.
- `zpektral`: `NEXT_PUBLIC_URL_API` com a URL do preview da API e `NEXT_PUBLIC_URL_SITE` com a do próprio site.

```powershell
cd ..\frontend
npx vercel@latest
```

Como as variáveis `NEXT_PUBLIC_*` entram no build, o site precisa de um deploy novo depois de definidas.

## 3. O que conferir em homologação

1. Smoke com dados reais apontando para o preview: em `frontend`, trocar `SITE` e `API` em `playwright.real.config.ts` pelas URLs de preview (ou rodar a mesma suíte local) e conferir as três verificações.
2. Busca com CEP de outra região (por exemplo `69900-000`): quando ninguém entrega, a tela diz "Nenhuma loja entrega no CEP".
3. `GET /ofertas/quedas` responde 200 (lista vazia é esperada no começo).
4. No branch `homologacao`, `select count(*) from historico_precos where consulta is not null` cresce depois das buscas, e nenhum texto tem e-mail ou sequência longa de números.

Com tudo certo, seguir `docs/implantacao.md` para produção.
