import argparse
import asyncio
from collections import Counter
from pathlib import Path

from app.busca import ServicoBusca
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes import criar_fontes
from app.relevancia import (
    CORES,
    MARCAS_VAZIAS,
    PALAVRAS_VAZIAS,
    UNIDADES,
    _produtos,
    _termos_brutos,
    normalizar,
    termos_do_texto,
)
from scripts.gerar_palavras import CONSULTAS

DESTINO = Path(__file__).resolve().parent.parent / "app" / "dados" / "marcas.txt"
# palavras comuns que alguma loja cadastra como marca
PALAVRAS_COMUNS = frozenset(
    """
    above ace ala bee champ charming euro even festive flick fortaleza future fuzz gang grow
    gum honor houston latina life lucky matrix mor mosaico optimum paixao parana quiz repo
    secar snob swift tron trust uau usual van vert vigor vitoria vogue warrior worker zebra
    """.split()
)
# categorias em que a pessoa costuma escrever a marca na busca
MAIS_CONSULTAS = """
smartphone|tablet|smartwatch|videogame|caixa de som|headset|teclado|mouse|impressora|roteador
lavadora|micro-ondas|liquidificador|batedeira|cafeteira|ar condicionado|ferro de passar
secador de cabelo|chapinha|barbeador|escova dental eletrica|purificador de agua|cooktop
geladeira inox|freezer|lava loucas|forno eletrico|panela eletrica|sanduicheira|ventilador
tenis masculino|tenis feminino|chinelo|sandalia|bolsa|oculos de sol|calca jeans|camisa polo
desodorante|sabonete|creme dental|hidratante|maquiagem|esmalte|racao gato|racao cachorro
cerveja|cafe|chocolate|biscoito|sabao em po|amaciante|papel higienico|leite em po
furadeira|parafusadeira|serra|lixadeira|chuveiro|torneira|lampada|fechadura
"""


async def coletar(consultas: list[str]) -> list[tuple[str, str]]:
    config = Configuracoes(_env_file=None)
    http = ClienteHttp(config)
    servico = ServicoBusca(criar_fontes(http, config), config)
    pares: set[tuple[str, str]] = set()
    try:
        for consulta in consultas:
            trabalho, _ = servico.iniciar(consulta, None)
            await trabalho.aguardar()
            pares.update((o.titulo, o.marca or "") for o in trabalho.ofertas)
            print(f"{consulta}: {len(pares)} títulos", flush=True)
    finally:
        await http.fechar()
    return sorted(pares)


def marcas(pares: list[tuple[str, str]], minimo: int, precisao: float) -> list[str]:
    """Marcas de uma palavra que, quando aparecem num título, quase sempre são a marca dele.

    "samsung" num título é quase sempre um produto Samsung; "power" ou "max" aparecem em
    produtos de muitas marcas e ficam de fora mesmo que alguma loja use como marca. A conta
    usa só os títulos com marca informada. Marca nova só sai de cadastro de uma palavra: "le"
    de "Le Lis" ou "sempre" de "Sempre Livre" seriam tomadas por marca em qualquer título.
    """
    por_marca: Counter[str] = Counter()
    no_titulo: Counter[str] = Counter()
    acertos: Counter[str] = Counter()
    for titulo, marca in pares:
        if not marca or normalizar(marca) in MARCAS_VAZIAS:
            continue
        termos_titulo = set(termos_do_texto(titulo))
        termos_marca = _termos_brutos(marca)
        no_titulo.update(termos_titulo)
        acertos.update(termos_titulo.intersection(termos_marca))
        if len(termos_marca) == 1 and _candidata(termos_marca[0]):
            por_marca[termos_marca[0]] += 1
    return sorted(
        m
        for m, n in por_marca.items()
        if n >= minimo and no_titulo[m] and acertos[m] / no_titulo[m] >= precisao
    )


def _candidata(termo: str) -> bool:
    return (
        len(termo) >= 2
        and not termo.isdigit()
        and termo not in CORES
        and termo not in UNIDADES
        and termo not in PALAVRAS_VAZIAS
        and termo not in _produtos()
        and termo not in PALAVRAS_COMUNS
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grava as marcas de uma palavra vistas em produtos reais; a relevância "
        "esconde outra marca quando a busca pede uma."
    )
    parser.add_argument("--minimo", type=int, default=5, help="títulos distintos da marca")
    parser.add_argument("--precisao", type=float, default=0.6)
    args = parser.parse_args()
    texto = (CONSULTAS + MAIS_CONSULTAS).replace("\n", "|").strip("|")
    consultas = list(dict.fromkeys(c.strip() for c in texto.split("|") if c.strip()))
    lista = marcas(asyncio.run(coletar(consultas)), args.minimo, args.precisao)
    DESTINO.write_text("\n".join(lista) + "\n", "utf-8", newline="\n")
    print(f"{len(lista)} marcas em {DESTINO}")


if __name__ == "__main__":
    main()
