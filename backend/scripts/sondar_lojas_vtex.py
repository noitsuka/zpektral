import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.parse import quote

import httpx

AGENTE = "zpektral"
CAMINHOS = (
    "/api/io/_v/api/intelligent-search/product_search/",
    "/api/catalog_system/pub/products/search",
    "/api/checkout/pub/orderForms/simulation",
)
# as URLs como app/fontes/vtex.py as monta: regras com curinga olham a consulta inteira
EXEMPLOS = (
    CAMINHOS[0] + "?query=fone&count=30&page=1&locale=pt-BR&hideUnavailableItems=true",
    CAMINHOS[1] + "?ft=fone&_from=0&_to=29",
    CAMINHOS[2],
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
    "brinquedos": "boneca",
    "auto": "pneu",
    "otica": "oculos",
    "joias": "anel",
    "papelaria": "caderno",
    "pet": "racao",
    "geral": "fone",
}
TERMOS_RESERVA = ("kit", "preto")
SIMULACOES = 3


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
    busca: str = "auto"
    aprovada: bool = False
    erros: list[str] = field(default_factory=list)


def _regras(texto: str, agente: str) -> list[tuple[bool, str]]:
    grupos: list[tuple[set[str], list[tuple[bool, str]]]] = []
    lendo_regras = True
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if ":" not in linha:
            continue
        chave, valor = (p.strip() for p in linha.split(":", 1))
        chave = chave.lower()
        if chave == "user-agent":
            if lendo_regras:
                grupos.append((set(), []))
                lendo_regras = False
            grupos[-1][0].add(valor.lower())
        elif chave in ("allow", "disallow") and grupos:
            lendo_regras = True
            if valor:
                grupos[-1][1].append((chave == "allow", valor))
    for nome in (agente, "*"):
        if any(nome in agentes for agentes, _ in grupos):
            return [r for agentes, regras in grupos if nome in agentes for r in regras]
    return []


def _casa(padrao: str, caminho: str) -> bool:
    corpo = re.escape(padrao.removesuffix("$")).replace(r"\*", ".*")
    return re.match(corpo + ("$" if padrao.endswith("$") else ""), caminho) is not None


def proibido_pelo_robots(texto: str, agente: str = AGENTE) -> list[str]:
    regras = _regras(texto, agente)
    proibidos = []
    for caminho, exemplo in zip(CAMINHOS, EXEMPLOS, strict=True):
        casadas = [(len(padrao), permite) for permite, padrao in regras if _casa(padrao, exemplo)]
        if not max(casadas, default=(0, True))[1]:
            proibidos.append(caminho)
    return proibidos


async def _buscar(
    cliente: httpx.AsyncClient, base: str, termo: str, r: Resultado, proibidos: list[str]
) -> list:
    if CAMINHOS[0] not in proibidos:
        try:
            resposta = await cliente.get(
                f"{base}{CAMINHOS[0]}?query={quote(termo)}&count=3&page=1&locale=pt-BR"
                "&hideUnavailableItems=true"
            )
            if resposta.status_code != 200:
                r.erros.append(f"inteligente {termo}: HTTP {resposta.status_code}")
            elif "json" in resposta.headers.get("content-type", ""):
                produtos = resposta.json().get("products") or []
                if produtos:
                    r.inteligente = len(produtos)
                    return produtos
        except (httpx.HTTPError, ValueError) as excecao:
            r.erros.append(f"inteligente: {type(excecao).__name__}")
    if CAMINHOS[1] in proibidos:
        return []
    resposta = await cliente.get(f"{base}{CAMINHOS[1]}?ft={quote(termo)}&_from=0&_to=2")
    if resposta.status_code in (200, 206) and resposta.text.lstrip().startswith("["):
        produtos = resposta.json()
        r.legada = len(produtos)
        return produtos
    r.erros.append(f"legada {termo}: HTTP {resposta.status_code}")
    return []


def _com_estoque(produtos: list) -> list[tuple[str, str]]:
    return [
        (item.get("itemId"), vendedor.get("sellerId"))
        for produto in produtos
        for item in produto.get("items") or []
        for vendedor in item.get("sellers") or []
        if (vendedor.get("commertialOffer") or {}).get("AvailableQuantity")
    ]


async def sondar(cliente: httpx.AsyncClient, loja: dict, cep: str) -> Resultado:
    r = Resultado(loja["id"], loja["nome"], loja["dominio"], loja.get("segmento", "geral"))
    base = f"https://{r.dominio}"
    termos = (TERMOS.get(r.segmento, "fone"), *TERMOS_RESERVA)
    try:
        robots = await cliente.get(f"{base}/robots.txt")
        # RFC 9309: 4xx libera tudo; 5xx e 429 valem como proibição total
        if robots.status_code >= 500 or robots.status_code == 429:
            r.robots = f"HTTP {robots.status_code}"
            return r
        bloqueados = proibido_pelo_robots(robots.text) if robots.status_code == 200 else []
        r.robots = "proíbe " + ", ".join(bloqueados) if bloqueados else "ok"
        if CAMINHOS[2] in bloqueados or (CAMINHOS[0] in bloqueados and CAMINHOS[1] in bloqueados):
            return r
        produtos: list = []
        for termo in termos:
            produtos = await _buscar(cliente, base, termo, r, bloqueados)
            if _com_estoque(produtos):
                break
        if not produtos:
            return r
        if CAMINHOS[1] in bloqueados:
            r.busca = "is"
        elif CAMINHOS[0] in bloqueados or not r.inteligente:
            r.busca = "legacy"
        r.frete = "sem estoque"
        canal = f"?sc={loja['sc']}" if loja.get("sc") else ""
        dados: dict = {}
        for sku, vendedor in _com_estoque(produtos)[:SIMULACOES]:
            simulacao = await cliente.post(
                f"{base}{CAMINHOS[2]}{canal}",
                json={
                    "items": [{"id": sku, "quantity": 1, "seller": vendedor}],
                    "postalCode": cep,
                    "country": "BRA",
                },
            )
            if simulacao.status_code != 200:
                r.frete = f"HTTP {simulacao.status_code}"
                break
            dados = simulacao.json()
            slas = [s for info in dados.get("logisticsInfo") or [] for s in info.get("slas") or []]
            r.frete = f"{len(slas)} opções" if slas else "sem opções"
            if slas:
                r.aprovada = True
                break
        else:
            codigos = {m.get("code") for m in (dados.get("messages") or []) if m.get("code")}
            if codigos:
                r.erros.append("simulação: " + ",".join(sorted(codigos)))
    except (httpx.HTTPError, ValueError) as excecao:
        r.erros.append(type(excecao).__name__)
    return r


async def executar(candidatas: list[dict], cep: str, paralelas: int) -> list[Resultado]:
    vagas = asyncio.Semaphore(paralelas)
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers={"user-agent": "zpektral/0.1 (+https://github.com/noitsuka/zpektral)"},
        # sem guardar cookies: um valor com acento (Renner) quebrava a requisição seguinte
        cookies=CookieJar(DefaultCookiePolicy(allowed_domains=[])),
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
            f"{situacao}{r.id:22} robots={r.robots:10} busca={r.busca:6} is={r.inteligente} "
            f"legada={r.legada} frete={r.frete} {' '.join(r.erros)}"
        )
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            json.dump([asdict(r) for r in resultados], arquivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
