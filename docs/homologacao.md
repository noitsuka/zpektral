# Homologação isolada da produção

## Estado em 20/11/2026

- **No ar para o PR #1** (`integracoes/marketplaces`):
  - site `https://zpektral-homologacao.vercel.app`, preview com Vercel Authentication (abre com login na Vercel);
  - API `https://zpektral-api-homologacao.vercel.app`, preview pública por uma exceção de proteção só desse alias.
- **Banco:** branch `homologacao` do Neon, criado do principal em 20/11/2026.
  - A senha do papel foi trocada só nele: a URL da homologação não abre o banco principal.
  - O texto das buscas herdado da produção (`consulta`) foi apagado no branch.
  - A migração `0004` foi aplicada só nele, com o ponto de recuperação `homologacao-antes-0004` (branch sem compute) criado antes. O principal continua na `0003`.
- **Vercel:**
  - variáveis só de Preview: `DATABASE_URL` e `DATABASE_URL_UNPOOLED` (sensíveis), `ORIGENS_CORS` e `CONFIAR_PROXY` na API; `NEXT_PUBLIC_URL_API` e `NEXT_PUBLIC_URL_SITE` no site;
  - nenhuma variável de Mercado Livre, Shopee ou eBay em nenhum ambiente; Production e Development não mudaram;
  - os dois projetos seguem sem Git ligado: um push não publica nada.

## Ambientes

| Ambiente | Banco | API | Site |
|---|---|---|---|
| Desenvolvimento | PostgreSQL local (`docs/desenvolvimento.md`) ou SQLite | `uvicorn` local | `npm run dev` |
| Homologação | branch `homologacao` do Neon | `zpektral-api-homologacao.vercel.app` (preview) | `zpektral-homologacao.vercel.app` (preview) |
| Produção | branch principal do Neon | `zpektral-api.vercel.app` | `zpektral.vercel.app` |

## 1. Banco de homologação (Neon)

1. Criar o branch a partir do principal, sem imprimir credenciais: `npx neonctl branches create --name homologacao --parent <principal> --no-secrets`.
2. Trocar a senha do papel **só no branch novo**: `npx neonctl roles reset-password neondb_owner --branch homologacao`. O branch herda a senha do principal; sem a troca, a URL da homologação também abriria a produção.
3. No branch novo, apagar o texto das buscas herdado: `update historico_precos set consulta = null where consulta is not null`.
4. Conferir o alvo antes de migrar. A configuração dá prioridade a `DATABASE_URL_UNPOOLED` sobre `DATABASE_URL`: um valor esquecido na sessão do PowerShell migraria outro banco sem aviso.

```powershell
cd backend
Remove-Item Env:DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
$env:DATABASE_URL = "<url direta do branch homologacao>"
.venv\Scripts\python.exe -c "from app.configuracao import obter_configuracoes as c; from sqlalchemy.engine import make_url as m; u = m(c().url_banco); print('alvo:', u.host, u.database)"
```

O host impresso (`ep-...`) precisa ser o do branch `homologacao`. Cada branch tem um endpoint próprio.

5. Antes de uma migração, criar o ponto de recuperação: `npx neonctl branches create --name homologacao-antes-<versão> --parent homologacao --no-compute --no-secrets`. Só então:

```powershell
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
Remove-Item Env:DATABASE_URL
```

`check` deve dizer `No new upgrade operations detected.`

## 2. Vercel: variáveis e proteção

- Criar as variáveis com `npx vercel env add <NOME> --project <projeto> --environment preview`, mandando o valor pela entrada padrão (nunca pela linha de comando). As duas URLs do banco vão com `--sensitive`.
- A integração do Neon com `zpektral-api` vale só para Production. Se ela voltar a valer para Preview, um preview usaria o banco de produção.
- **Proteção:** a Vercel Authentication continua ligada nos dois projetos. Só o alias da API de homologação fica fora dela, em Settings > Deployment Protection > Deployment Protection Exceptions (disponível no Hobby, só pelo painel). Sem a exceção, o navegador recebe o redirecionamento para o login em vez da resposta, e a busca do site de preview falha.

## 3. Publicar em preview com nomes fixos

Os nomes fixos evitam um ciclo: o CORS da API e a `NEXT_PUBLIC_URL_API` do site já apontam para eles antes de qualquer deploy.

```powershell
git worktree add --detach <pasta temporária> <commit>
# copiar backend\.vercel e frontend\.vercel do checkout principal para a mesma pasta da worktree
cd <pasta temporária>\backend
npx vercel@latest deploy
npx vercel@latest alias set <url do preview da API> zpektral-api-homologacao.vercel.app
cd ..\frontend
npx vercel@latest deploy
npx vercel@latest alias set <url do preview do site> zpektral-homologacao.vercel.app
```

- A worktree garante que só os arquivos do commit sobem, sem `.env` nem arquivos locais.
- Sem `--prod`, o comando cria um deploy de preview. Se a CLI oferecer ligar o repositório Git, **responda não**: com o Git ligado, cada push passaria a publicar.
- Depois, `npx vercel@latest project inspect zpektral-api` e `npx vercel@latest project inspect zpektral` devem continuar com `Git Repository: Not connected`.

Para republicar só a API, repita o deploy e o `alias set` dela. A exceção de proteção é do alias, então continua valendo.

## 4. O que conferir em homologação

1. `https://zpektral-api-homologacao.vercel.app/saude` responde 200, e `/lojas` mostra Mercado Livre, Shopee e eBay desativados.
2. A URL própria de cada deploy, inclusive os antigos de produção, redireciona para o login da Vercel.
3. Smoke com lojas reais contra o site de homologação, que é protegido:
   - criar um segredo de bypass só no projeto do site (Settings > Deployment Protection > Protection Bypass for Automation);
   - pedir a página com os cabeçalhos `x-vercel-protection-bypass` e `x-vercel-set-bypass-cookie: true` e guardar o cookie devolvido num arquivo de estado do Playwright;
   - rodar o smoke e **revogar o segredo** em seguida.

```powershell
cd frontend
$env:SITE_REMOTO = "https://zpektral-homologacao.vercel.app"
$env:ESTADO_BYPASS = "<arquivo de estado com o cookie>"
npx playwright test -c playwright.real.config.ts
Remove-Item Env:SITE_REMOTO, Env:ESTADO_BYPASS
```

   Espera-se 8 testes passando (4 no desktop e 4 no celular). Um deles mede o CLS de uma busca ao vivo e exige menos de 0,1.

4. Busca com CEP de outra região (por exemplo `69900-001`, em Rio Branco): quando ninguém entrega, a tela diz "Nenhuma loja entrega no CEP".
5. Isolamento do histórico: depois de uma busca só na homologação, as linhas com aquela `consulta` aparecem no branch `homologacao` e nenhuma no principal (consulta só de leitura no principal).

## 5. Desmontar

1. Remover os aliases `zpektral-homologacao` e `zpektral-api-homologacao` e os previews. A exceção de proteção sai junto com o alias.
2. Apagar as variáveis só de Preview dos dois projetos.
3. Apagar os branches `homologacao` e `homologacao-antes-<versão>` do Neon.
