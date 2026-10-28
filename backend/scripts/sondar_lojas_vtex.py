import argparse
import asyncio
import json
from dataclasses import asdict, dataclass, field
from urllib.parse import quote

import httpx

CAMINHOS = (
    "/api/io/_v/api/intelligent-search/product_search/",
    "/api/catalog_system/pub/products/search",
    "/api/checkout/pub/orderForms/simulation",
)
TERMOS = {
    "eletro": "ventilador",
    "tecnologia": "fone",
    "casa": "panela",
    "construcao": "torneira",
    "moda": "camiseta",
    "esporte": "tenis",
    "beleza": "shampoo",
    "farmacia": "protetor solar",
    "mercado": "arroz",
    "infantil": "boneca",
    "auto": "pneu",
    "geral": "fone",
}
TERMOS_RESERVA = ("kit", "preto")


@dataclass
class Resultado:
    id: str
    nome: str
    dominio: str
    segmento: str
    robots: str = "?"
    inteligente: int = 0
    legada: int = 0
    frete: str = "?"
    aprovada: bool = False
    erros: list[str] = field(default_factory=list)


def proibido_pelo_robots(texto: str) -> list[str]:
    grupo, proibidos = False, []
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha or ":" not in linha:
            continue
        chave, valor = (p.strip() for p in linha.split(":", 1))
        chave = chave.lower()
        if chave == "user-agent":
            grupo = valor == "*"
        elif grupo and chave == "disallow" and valor:
            proibidos.extend(c for c in CAMINHOS if c.startswith(valor.rstrip("*")))
    return proibidos


async def _buscar(cliente: httpx.AsyncClient, base: str, termo: str, r: Resultado) -> list:
    try:
        resposta = await cliente.get(
            f"{base}{CAMINHOS[0]}?query={quote(termo)}&count=3&page=1&locale=pt-BR"
            "&hideUnavailableItems=true"
        )
        if resposta.status_code == 200 and "json" in resposta.headers.get("content-type", ""):
            produtos = resposta.json().get("products") or []
            if produtos:
                r.inteligente = len(produtos)
                return produtos
    except (httpx.HTTPError, ValueError) as excecao:
        r.erros.append(f"inteligente: {type(excecao).__name__}")
    resposta = await cliente.get(f"{base}{CAMINHOS[1]}?ft={quote(termo)}&_from=0&_to=2")
    if resposta.status_code in (200, 206) and resposta.text.lstrip().startswith("["):
        produtos = resposta.json()
        r.legada = len(produtos)
        return produtos
    r.erros.append(f"legada {termo}: HTTP {resposta.status_code}")
    return []


async def sondar(cliente: httpx.AsyncClient, loja: dict, cep: str) -> Resultado:
    r = Resultado(loja["id"], loja["nome"], loja["dominio"], loja.get("segmento", "geral"))
    base = f"https://{r.dominio}"
    termos = (TERMOS.get(r.segmento, "fone"), *TERMOS_RESERVA)
    try:
        robots = await cliente.get(f"{base}/robots.txt")
        bloqueados = proibido_pelo_robots(robots.text) if robots.status_code == 200 else []
        r.robots = "proíbe " + ", ".join(bloqueados) if bloqueados else "ok"
        if bloqueados:
            return r
        produtos: list = []
        for termo in termos:
            produtos = await _buscar(cliente, base, termo, r)
            if produtos:
                break
        if not produtos:
            return r
        item = (produtos[0].get("items") or [{}])[0]
        vendedor = (item.get("sellers") or [{}])[0].get("sellerId") or "1"
        simulacao = await cliente.post(
            f"{base}{CAMINHOS[2]}",
            json={
                "items": [{"id": item.get("itemId"), "quantity": 1, "seller": vendedor}],
                "postalCode": cep,
                "country": "BRA",
            },
        )
        if simulacao.status_code == 200:
            logistica = simulacao.json().get("logisticsInfo") or []
            slas = [s for info in logistica for s in info.get("slas") or []]
            r.frete = f"{len(slas)} opções" if slas else "sem opções"
            r.aprovada = bool(slas)
        else:
            r.frete = f"HTTP {simulacao.status_code}"
    except (httpx.HTTPError, ValueError) as excecao:
        r.erros.append(type(excecao).__name__)
    return r


async def executar(candidatas: list[dict], cep: str, paralelas: int) -> list[Resultado]:
    vagas = asyncio.Semaphore(paralelas)
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers={"user-agent": "zpektral/0.1 (+https://github.com/noitsuka/zpektral)"},
    ) as cliente:

        async def uma(loja: dict) -> Resultado:
            async with vagas:
                return await sondar(cliente, loja, cep)

        return await asyncio.gather(*(uma(c) for c in candidatas))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Confere robots.txt, busca e simulação de frete de lojas VTEX candidatas."
    )
    parser.add_argument("candidatas", help="JSON com id, nome, dominio e segmento")
    parser.add_argument("--cep", default="01310100")
    parser.add_argument("--paralelas", type=int, default=6)
    parser.add_argument("--saida", help="grava o relatório completo em JSON")
    args = parser.parse_args()
    with open(args.candidatas, encoding="utf-8") as arquivo:
        candidatas = json.load(arquivo)
    resultados = asyncio.run(executar(candidatas, args.cep, args.paralelas))
    for r in sorted(resultados, key=lambda x: (not x.aprovada, x.id)):
        situacao = "OK " if r.aprovada else "-- "
        print(
            f"{situacao}{r.id:22} robots={r.robots:10} is={r.inteligente} "
            f"legada={r.legada} frete={r.frete} {' '.join(r.erros)}"
        )
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            json.dump([asdict(r) for r in resultados], arquivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
