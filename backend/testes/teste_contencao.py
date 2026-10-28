import asyncio

from app.busca import ServicoBusca, sanear
from app.fontes.base import montar_ofertas
from app.fontes.buscape import FonteBuscape
from app.modelos import Loja, Oferta
from testes.conftest import contexto
from testes.falsos import FonteFalsa


def _oferta(**campos) -> Oferta:
    base = {
        "id": "x:1",
        "titulo": "Air Fryer",
        "link": "https://loja.com.br/p",
        "loja": Loja("x", "X"),
        "preco": 1000,
    }
    return Oferta(**{**base, **campos})


def teste_sanear_aguenta_tipos_errados_vindos_da_loja():
    ofertas = [
        _oferta(id="a", imagem={"url": "x"}),
        _oferta(id="b", titulo=123),
        _oferta(id="c", preco="1000"),
        _oferta(id="d", link=None),
    ]
    saida = sanear(ofertas)
    assert [o.id for o in saida] == ["a"]
    assert saida[0].imagem is None


def teste_montar_ofertas_pula_so_a_entrada_quebrada():
    def montar(entrada, posicao):
        return _oferta(id=f"x:{posicao}", preco=int(entrada))

    ofertas = montar_ofertas("x", ["100", "abc", "300"], montar)
    assert [o.preco for o in ofertas] == [100, 300]


class FonteComDefeito(FonteFalsa):
    async def buscar(self, ctx, previa=None):
        return [_oferta(id="defeito:1", titulo=object())]


async def teste_defeito_numa_fonte_nao_encerra_a_busca_antes_das_outras(config):
    lenta = FonteFalsa("lenta", [("Air Fryer Mondial", 30000)], atraso=0.1)
    servico = ServicoBusca([FonteComDefeito("defeito"), lenta], config)
    trabalho, _ = servico.iniciar("air fryer", None)
    await asyncio.sleep(0.02)
    assert not trabalho.terminou
    await trabalho.aguardar()
    assert {r.id for r in trabalho.relatorios} == {"defeito", "lenta"}
    assert [o.loja.id for o in trabalho.ofertas] == ["lenta"]


async def teste_buscape_recusa_link_absoluto_ou_de_outro_host(http, config):
    fonte = FonteBuscape(http, config)
    ctx = contexto("air fryer")
    base = {"price": 300, "name": "Air Fryer", "bestOffer": {"merchantName": "Loja"}}
    from app.fontes.buscape import _caminho

    assert _caminho({**base, "url": "https://outro.com/x"}) is None
    assert _caminho({**base, "url": "//outro.com/x"}) is None
    oferta = fonte._da_vitrine({**base, "url": "/air-fryer"}, 0, ctx)
    assert oferta.link == "https://www.buscape.com.br/air-fryer"
