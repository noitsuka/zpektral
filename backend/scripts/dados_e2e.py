import asyncio
from pathlib import Path

from app.api.esquemas import info_das_fontes
from app.api.eventos import eventos_da_busca
from app.busca import ServicoBusca
from app.cliente_http import ErroExterno
from app.configuracao import Configuracoes
from app.fontes.base import ContextoBusca, Previa
from app.modelos import (
    Condicao,
    Endereco,
    Frete,
    Loja,
    Oferta,
    Parcelamento,
    StatusFrete,
)
from app.ordenacao import Filtros

DESTINO = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "dados"
BH = Endereco("30130010", "Avenida Afonso Pena", "Centro", "Belo Horizonte", "MG")
RIO_BRANCO = Endereco("69900000", None, None, "Rio Branco", "AC")
MARCAS = ["Brastemp", "Consul", "Electrolux", "Samsung", "LG", "Panasonic"]


def frete_cotado(valor: int, dias: int) -> Frete:
    return Frete(
        StatusFrete.CALCULADO, valor=valor, prazo=f"até {dias} dias úteis", prazo_dias=dias
    )


class LojaFalsa:
    def __init__(self, id_: str, nome: str, ofertas=(), erro: Exception | None = None):
        self.id, self.nome, self._ofertas, self._erro = id_, nome, list(ofertas), erro

    @property
    def ativa(self) -> bool:
        return True

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        if self._erro:
            raise self._erro
        saida = []
        for i, (titulo, preco, extras) in enumerate(self._ofertas):
            saida.append(
                Oferta(
                    id=f"{self.id}:{i}:1",
                    titulo=titulo,
                    link=f"https://{self.id}.example/produto/{i}",
                    loja=Loja(self.id, self.nome),
                    preco=preco,
                    relevancia=ctx.relevancia_de(titulo),
                    posicao=i,
                    consultado_em="2026-11-18T12:00:00+00:00",
                    **extras,
                ).consolidar()
            )
        return saida


def geladeiras(loja: int, quantas: int, frete: Frete) -> list:
    return [
        (
            f"Geladeira Frost Free {MARCAS[(i + loja) % len(MARCAS)]} {300 + 10 * i}L Inox 110V",
            250_000 + 7_000 * i + 1_300 * loja,
            {
                "frete": frete,
                "preco_pix": 240_000 + 7_000 * i + 1_300 * loja,
                "parcelamento": Parcelamento(10, 25_000 + 700 * i, 250_000 + 7_000 * i, False),
            },
        )
        for i in range(quantas)
    ]


PROMOCAO = (
    "Geladeira Frost Free Electrolux 400L Inox 110V",
    199_900,
    {
        "frete": frete_cotado(0, 3),
        "preco_original": 349_900,
        "preco_pix": 189_900,
        "promocoes": ["SUPEROFERTA"],
        "preco_valido_ate": "2026-11-21T02:59:00+00:00",
    },
)
SEM_COTACAO = (
    "Geladeira Frost Free Consul 340L Branca 110V",
    150_000,
    {"frete": Frete(StatusFrete.NAO_INFORMADO)},
)
PARECIDA = ("Geladeira Duplex Consul Cycle Defrost 334L Branca 110V", 180_000, {})

CENARIOS = {
    "busca-geladeira": (
        "geladeira frost free",
        BH,
        [
            LojaFalsa("alfa", "Loja Alfa", [*geladeiras(0, 25, frete_cotado(4_990, 5)), PARECIDA]),
            LojaFalsa("beta", "Loja Beta", [PROMOCAO, *geladeiras(1, 20, frete_cotado(2_990, 7))]),
            LojaFalsa("gama", "Loja Gama", [SEM_COTACAO, *geladeiras(2, 10, frete_cotado(0, 10))]),
            LojaFalsa("delta", "Loja Delta", erro=ErroExterno("falhou", 500)),
            LojaFalsa("epsilon", "Loja Epsilon", erro=ErroExterno("recusou", 403)),
        ],
    ),
    "busca-sem-resultado": (
        "xyzzy quasar",
        None,
        [LojaFalsa("alfa", "Loja Alfa"), LojaFalsa("beta", "Loja Beta")],
    ),
    "busca-nao-entrega": (
        "geladeira frost free",
        RIO_BRANCO,
        [
            LojaFalsa("alfa", "Loja Alfa", geladeiras(0, 6, Frete(StatusFrete.NAO_ENTREGA))),
            LojaFalsa("beta", "Loja Beta", geladeiras(1, 4, Frete(StatusFrete.NAO_ENTREGA))),
        ],
    ),
    "busca-lojas-fora": (
        "geladeira frost free",
        None,
        [
            LojaFalsa("alfa", "Loja Alfa", erro=ErroExterno("falhou", 500)),
            LojaFalsa("beta", "Loja Beta", erro=ErroExterno("recusou", 429)),
        ],
    ),
}


async def gravar(nome: str, consulta: str, endereco: Endereco | None, lojas: list) -> None:
    servico = ServicoBusca(lojas, Configuracoes(_env_file=None))
    trabalho, _ = servico.iniciar(consulta, endereco)
    await trabalho.aguardar()
    filtros = Filtros(condicoes=frozenset(Condicao), apenas_disponiveis=False)
    corpo = b"".join(
        [e async for e in eventos_da_busca(trabalho, endereco, info_das_fontes(servico), filtros)]
    )
    (DESTINO / f"{nome}.sse").write_bytes(corpo)


async def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, (consulta, endereco, lojas) in CENARIOS.items():
        await gravar(nome, consulta, endereco, lojas)
        print(nome, (DESTINO / f"{nome}.sse").stat().st_size, "bytes")


if __name__ == "__main__":
    asyncio.run(main())
