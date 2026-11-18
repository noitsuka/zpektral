# Ambiente de desenvolvimento sem Docker

O projeto roda com Python 3.12+, Node.js 24 e um PostgreSQL 17. O Docker é opcional: a CI ainda constrói a imagem, mas nada no desenvolvimento depende dele.

## Banco

O pacote portátil oficial do PostgreSQL para Windows não pede administrador, não cria serviço e não precisa de reinício. Baixe `postgresql-17.12-1-windows-x64-binaries.zip` pelo link "zip archive" de https://www.postgresql.org/download/windows/ e descompacte fora do repositório.

```powershell
pgsql\bin\initdb.exe -D data -U postgres -A trust -E UTF8 --locale=C -c listen_addresses=127.0.0.1 -c port=5433
pgsql\bin\pg_ctl.exe -D data -l servidor.log start
pgsql\bin\createdb.exe -h 127.0.0.1 -p 5433 -U postgres zpektral
```

O acesso sem senha só vale para 127.0.0.1. Para parar: `pgsql\bin\pg_ctl.exe -D data stop`.

## API

```powershell
cd backend
uv venv .venv
uv pip install --python .venv -e ".[dev,navegador]"
$env:DATABASE_URL = "postgresql://postgres@127.0.0.1:5433/zpektral"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Sem `DATABASE_URL`, o histórico vai para um SQLite local. Testes: `.venv\Scripts\python.exe -m pytest -q`; os que consultam lojas de verdade rodam com `-m live`. A CI repete as migrações com `alembic upgrade head`, `alembic check`, `alembic downgrade base` e `alembic upgrade head`.

## Site

```powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_URL_API = "http://localhost:8000"
npm run dev
```

## Medições

- `python -m scripts.medir_busca`: latência, tempo até a primeira oferta relevante, requisições e memória da busca.
- `python -m scripts.desempenho`: custo da pontuação, do agrupamento e da ordenação com ofertas sintéticas.
- `python -m scripts.sondar_lojas_vtex <arquivo.json>`: confere robots.txt, busca e frete de lojas candidatas.
