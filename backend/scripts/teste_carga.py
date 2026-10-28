import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx

FILTROS = [
    {},
    {"ordem": "menor_total"},
    {"ordem": "custo_beneficio", "pagamento": "pix"},
    {"frete": "calculado"},
    {"preco_max": "50000"},
    {"condicao": "novo,usado,recondicionado"},
    {"pagina": "2"},
]


async def cliente(api: httpx.AsyncClient, consulta: str, cep: str, fim: float, tempos, codigos):
    i = 0
    while time.perf_counter() < fim:
        parametros = {"q": consulta, "cep": cep, **FILTROS[i % len(FILTROS)]}
        inicio = time.perf_counter()
        try:
            resposta = await api.get("/busca", params=parametros)
            codigos[resposta.status_code] += 1
        except httpx.HTTPError as excecao:
            codigos[type(excecao).__name__] += 1
        tempos.append((time.perf_counter() - inicio) * 1000)
        i += 1


async def executar(args) -> None:
    limites = httpx.Limits(max_connections=args.clientes, max_keepalive_connections=args.clientes)
    async with httpx.AsyncClient(base_url=args.api, timeout=30, limits=limites) as api:
        aquecimento = await api.get(
            "/busca", params={"q": args.consulta, "cep": args.cep, "espera_ms": 30000}
        )
        aquecimento.raise_for_status()
        print(f"aquecido: {aquecimento.json()['total']} ofertas para {args.consulta!r}")

        tempos: list[float] = []
        codigos: Counter = Counter()
        fim = time.perf_counter() + args.segundos
        await asyncio.gather(
            *(
                cliente(api, args.consulta, args.cep, fim, tempos, codigos)
                for _ in range(args.clientes)
            )
        )

    tempos.sort()
    p = lambda q: tempos[min(len(tempos) - 1, int(q * len(tempos)))]  # noqa: E731
    print(f"{len(tempos)} requisições em {args.segundos} s com {args.clientes} clientes")
    print(f"vazão: {len(tempos) / args.segundos:.0f} req/s")
    print(
        f"latência: p50 {p(0.5):.1f} ms · p95 {p(0.95):.1f} ms · p99 {p(0.99):.1f} ms"
        f" · média {statistics.fmean(tempos):.1f} ms"
    )
    print("respostas:", dict(codigos))
    if codigos.get(429):
        print("Houve 429: suba REQUISICOES_POR_MINUTO e RAJADA_REQUISICOES na API do teste.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga sobre buscas em cache: filtros, ordenação e paginação em memória."
    )
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--consulta", default="air fryer")
    parser.add_argument("--cep", default="30130010")
    parser.add_argument("--clientes", type=int, default=50)
    parser.add_argument("--segundos", type=int, default=15)
    asyncio.run(executar(parser.parse_args()))


if __name__ == "__main__":
    main()
