import argparse
import asyncio
from collections import Counter
from pathlib import Path

from app.relevancia import CORES, UNIDADES, _marcas, cabeca_do_titulo, termos_do_texto
from scripts.gerar_marcas import MAIS_CONSULTAS, coletar
from scripts.gerar_palavras import CONSULTAS

DADOS = Path(__file__).resolve().parent.parent / "app" / "dados"
DESTINO = DADOS / "frequencias.txt"
DESTINO_TIPOS = DADOS / "tipos.txt"
# livros, mídia e presentes, para "mangá", "volume", "graphic novel" ou "edição" contarem como
# palavras comuns, e não como nome raro
CONSULTAS_DE_MIDIA = """
manga|hq|livro infantil|box livros|jogo ps5|jogo nintendo switch|funko|lego|pelucia|caneca
camiseta|quadro decorativo|action figure|blu-ray|vinil|graphic novel|gibi|dvd|cd musica
livro de colorir|livro de receitas|biografia|romance|agenda|planner|album de figurinhas
jogo de tabuleiro|jogo xbox|camisa de time|chaveiro|poster|adesivo
"""


def frequencias(titulos: list[str], minimo: int) -> tuple[int, dict[str, int]]:
    """Em quantos títulos cada termo aparece, na forma que a relevância compara.

    O termo que fica abaixo do mínimo não entra no arquivo e conta como raro.
    """
    contagem: Counter[str] = Counter()
    for titulo in titulos:
        contagem.update(set(termos_do_texto(titulo)))
    return len(titulos), {t: n for t, n in contagem.items() if n >= minimo}


def tipos(titulos: list[str], minimo: int, fracao: float) -> list[str]:
    """Palavras que, quando aparecem num título, quase sempre o abrem: o tipo do produto.

    O anúncio brasileiro começa pelo que o produto é ("Caneca Demon Slayer", "Bola de Futebol
    Seleção Brasileira"). "Camisa" abre 96% dos títulos em que aparece; "manga" abre 2%, porque
    quase sempre é a manga curta da camiseta; "moto" abre 6%, porque vem de "Moto G85".
    """
    abre: Counter[str] = Counter()
    aparece: Counter[str] = Counter()
    for titulo in titulos:
        termos = termos_do_texto(titulo)
        aparece.update(set(termos))
        if cabeca := cabeca_do_titulo(termos):
            abre[cabeca] += 1
    marcas = _marcas()
    return sorted(
        t
        for t, n in abre.items()
        if n >= minimo
        and n / aparece[t] >= fracao
        and t.isalpha()
        and len(t) >= 3
        and t not in marcas
        and t not in CORES
        and t not in UNIDADES
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grava em quantos títulos reais cada termo aparece e quais palavras "
        "costumam abrir o título. Quando quase nenhuma loja tem o produto exato, a busca se "
        "reavalia dando menos peso ao termo comum, como 'mangá', do que ao nome raro, como "
        "'punpun', e deixa de fora o título que abre com outro tipo de produto."
    )
    parser.add_argument("--minimo", type=int, default=10, help="títulos distintos por termo")
    parser.add_argument("--minimo-tipo", type=int, default=20, help="títulos que o termo abre")
    parser.add_argument("--fracao-tipo", type=float, default=0.5)
    args = parser.parse_args()
    texto = (CONSULTAS + MAIS_CONSULTAS + CONSULTAS_DE_MIDIA).replace("\n", "|").strip("|")
    consultas = list(dict.fromkeys(c.strip() for c in texto.split("|") if c.strip()))
    titulos = sorted({titulo for titulo, _ in asyncio.run(coletar(consultas))})
    total, contagem = frequencias(titulos, args.minimo)
    linhas = [f"{t} {n}" for t, n in sorted(contagem.items())]
    DESTINO.write_text(f"{total}\n" + "\n".join(linhas) + "\n", "utf-8", newline="\n")
    lista = tipos(titulos, args.minimo_tipo, args.fracao_tipo)
    DESTINO_TIPOS.write_text("\n".join(lista) + "\n", "utf-8", newline="\n")
    print(f"{len(linhas)} termos de {total} títulos em {DESTINO}; {len(lista)} tipos")


if __name__ == "__main__":
    main()
