import argparse
import asyncio
import json
import statistics
import time
import tracemalloc
from collections import Counter

from app.busca import ServicoBusca
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes import criar_fontes

CONSULTAS = [
    "geladeira frost free",
    "smart tv 55",
    "air fryer",
    "notebook i5 16gb",
    "iphone 15 128gb",
    "furadeira de impacto",
    "estante para livros multy 4 prateleiras menta",
    "fralda pampers g",
    "tenis corrida masculino",
    "cadeira gamer",
]
RELEVANTE = 90


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p * (len(ordenados) - 1)))]


async def medir(consultas: list[str]) -> dict:
    config = Configuracoes(_env_file=None)
    http = ClienteHttp(config)
    requisicoes: Counter[str] = Counter()
    original = http._buscar

    async def contar(metodo, url, host, **argumentos):
        requisicoes[host] += 1
        return await original(metodo, url, host, **argumentos)

    http._buscar = contar
    servico = ServicoBusca(criar_fontes(http, config), config)
    linhas = []
    tracemalloc.start()
    try:
        for consulta in consultas:
            antes = sum(requisicoes.values())
            inicio = time.perf_counter()
            trabalho, do_cache = servico.iniciar(consulta, None)
            primeira = primeira_relevante = None
            async for lote in trabalho.acompanhar():
                agora = time.perf_counter() - inicio
                if lote.ofertas and primeira is None:
                    primeira = agora
                if primeira_relevante is None and any(
                    o.relevancia >= RELEVANTE for o in lote.ofertas
                ):
                    primeira_relevante = agora
            fim = time.perf_counter() - inicio
            inicio_cache = time.perf_counter()
            _, repetida = servico.iniciar(consulta, None)
            linhas.append(
                {
                    "consulta": consulta,
                    "primeira_oferta_s": primeira,
                    "primeira_relevante_s": primeira_relevante,
                    "conclusao_s": fim,
                    "ofertas": len(trabalho.ofertas),
                    "relevantes": sum(o.relevancia >= RELEVANTE for o in trabalho.ofertas),
                    "requisicoes": sum(requisicoes.values()) - antes,
                    "cache_na_repeticao": repetida and not do_cache,
                    "repeticao_ms": (time.perf_counter() - inicio_cache) * 1000,
                }
            )
            print(json.dumps(linhas[-1], ensure_ascii=False))
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        await http.fechar()
    conclusoes = [linha["conclusao_s"] for linha in linhas]
    relevantes = [
        linha["primeira_relevante_s"] for linha in linhas if linha["primeira_relevante_s"]
    ]
    return {
        "buscas": linhas,
        "conclusao_p50_s": statistics.median(conclusoes),
        "conclusao_p95_s": percentil(conclusoes, 0.95),
        "primeira_relevante_p50_s": statistics.median(relevantes) if relevantes else None,
        "primeira_relevante_p95_s": percentil(relevantes, 0.95) if relevantes else None,
        "sem_relevante": sum(linha["primeira_relevante_s"] is None for linha in linhas),
        "requisicoes_por_busca": statistics.mean(linha["requisicoes"] for linha in linhas),
        "cache_acertos": sum(linha["cache_na_repeticao"] for linha in linhas) / len(linhas),
        "memoria_pico_mb": pico / 1_048_576,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mede latência, primeira oferta relevante, requisições e memória da busca."
    )
    parser.add_argument("--saida", help="grava o relatório em JSON")
    args = parser.parse_args()
    resumo = asyncio.run(medir(CONSULTAS))
    print(json.dumps({k: v for k, v in resumo.items() if k != "buscas"}, indent=1))
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            json.dump(resumo, arquivo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
