import argparse
import asyncio
from collections import Counter
from pathlib import Path

from app.busca import ServicoBusca
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes import criar_fontes
from app.relevancia import normalizar

DESTINO = Path(__file__).resolve().parent.parent / "app" / "dados" / "palavras.txt"
CONSULTAS = """
geladeira|notebook|tenis corrida|shampoo|furadeira|sofa|estante|panela|fralda|smart tv|camiseta
colchao|perfume|cadeira gamer|bicicleta|celular|fone|mesa|guarda roupa|ventilador|secador
torneira|maquiagem|protetor solar|air fryer|fogao|aspirador|impressora|monitor|brinquedo
luminaria|tapete|jogo de cama|vestido|relogio|racao|pneu|tinta|livro|mochila
"""


async def coletar(consultas: list[str]) -> Counter[str]:
    config = Configuracoes(_env_file=None)
    http = ClienteHttp(config)
    servico = ServicoBusca(criar_fontes(http, config), config)
    titulos: set[str] = set()
    try:
        for consulta in consultas:
            trabalho, _ = servico.iniciar(consulta, None)
            await trabalho.aguardar()
            titulos.update(o.titulo for o in trabalho.ofertas)
    finally:
        await http.fechar()
    return Counter(p for t in titulos for p in set(normalizar(t).split()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grava as palavras que aparecem em títulos reais; o corretor não mexe nelas."
    )
    parser.add_argument("--minimo", type=int, default=2, help="títulos distintos por palavra")
    args = parser.parse_args()
    contagem = asyncio.run(coletar(CONSULTAS.replace("\n", "|").strip("|").split("|")))
    palavras = sorted(
        p for p, n in contagem.items() if n >= args.minimo and p.isalpha() and len(p) >= 6
    )
    DESTINO.write_text("\n".join(palavras) + "\n", "utf-8")
    print(f"{len(palavras)} palavras em {DESTINO}")


if __name__ == "__main__":
    main()
