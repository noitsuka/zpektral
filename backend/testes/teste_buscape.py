import re

import httpx
import pytest

from app.cliente_http import ErroExterno
from app.fontes.buscape import (
    FonteBuscape,
    ler_ofertas_do_produto,
    ler_resultados,
    url_de_busca,
)
from app.modelos import Origem, StatusFrete
from testes.conftest import contexto, gravacao_bytes

BUSCA = re.compile(r"https://www\.buscape\.com\.br/busca/.*")
PRODUTO = "https://www.buscape.com.br/fritadeira/fritadeira-eletrica-sem-oleo-mondial-afn-40-fb-capacidade-4l"
PROIBIDAS = re.compile(r"https://www\.buscape\.com\.br/(search|lead|ajax).*|.*[?&]q=.*")


@pytest.fixture
def buscape(simulador):
    proibidas = simulador.get(PROIBIDAS).mock(httpx.Response(500))
    simulador.get(BUSCA).mock(httpx.Response(200, content=gravacao_bytes("buscape_busca.html")))
    produto = simulador.get(PRODUTO).mock(
        httpx.Response(200, content=gravacao_bytes("buscape_produto.html"))
    )
    simulador.get(re.compile(r"https://www\.buscape\.com\.br/(?!busca/).+")).mock(
        httpx.Response(404)
    )
    return proibidas, produto


def teste_busca_usa_o_caminho_permitido_pelo_robots():
    assert url_de_busca("air fryer 4L") == "https://www.buscape.com.br/busca/air+fryer+4L"
    assert url_de_busca("café & leite") == "https://www.buscape.com.br/busca/caf%C3%A9+%26+leite"


def teste_ler_resultados_e_ofertas_do_produto():
    assert len(ler_resultados(gravacao_bytes("buscape_busca.html"))) == 10
    ofertas = ler_ofertas_do_produto(gravacao_bytes("buscape_produto.html"))
    assert ofertas and len({o["id"] for o in ofertas}) == len(ofertas)
    assert {o["sellerName"] for o in ofertas} == {"Amazon", "Magazine Luiza"}


def teste_pagina_sem_dados_e_erro():
    with pytest.raises(ErroExterno):
        ler_resultados(b"<html><body>captcha</body></html>")


async def teste_nunca_acessa_caminhos_proibidos(buscape, http, config):
    proibidas, _ = buscape
    await FonteBuscape(http, config).buscar(contexto("air fryer mondial"))
    assert not proibidas.called


async def teste_pagina_do_produto_traz_cada_loja_que_vende(buscape, http, config):
    _, produto = buscape
    ofertas = await FonteBuscape(http, config).buscar(contexto("air fryer mondial"))
    assert produto.called
    da_pagina = [o for o in ofertas if o.link == PRODUTO]
    assert {o.loja.nome for o in da_pagina} == {"Amazon", "Magazine Luiza"}
    assert len(da_pagina) > 1
    for o in ofertas:
        assert o.origem is Origem.COMPARADOR
        assert o.frete.status is StatusFrete.NAO_INFORMADO
        assert o.total_exato is False
        assert o.loja.id.startswith("buscape:")
    parceladas = [o for o in da_pagina if o.parcelamento]
    assert parceladas and all(o.parcelamento.total >= o.preco for o in parceladas)


async def teste_vitrine_chega_antes_das_paginas(buscape, http, config):
    previas = []
    await FonteBuscape(http, config).buscar(contexto("air fryer mondial"), previas.append)
    assert len(previas) == 1 and previas[0]


async def teste_lojistas_consultados_direto_ficam_guardados(buscape, http, config):
    tudo = await FonteBuscape(http, config).buscar(contexto("air fryer mondial"))
    do_magalu = {o.id for o in tudo if o.loja.nome == "Magazine Luiza"}
    assert do_magalu
    ctx, previas = contexto("air fryer mondial"), []
    filtradas = await FonteBuscape(http, config, lojas_diretas=["Magazine Luiza"]).buscar(
        ctx, previas.append
    )
    assert "Magazine Luiza" not in {o.loja.nome for o in filtradas}
    assert "Magazine Luiza" not in {o.loja.nome for previa in previas for o in previa}
    # guardadas para o caso de a fonte direta da loja falhar nesta busca
    assert {o.id for o in ctx.reservadas["buscape"]["magazineluiza"]} == do_magalu


async def teste_pagina_de_produto_fora_do_ar_mantem_a_vitrine(simulador, http, config):
    simulador.get(BUSCA).mock(httpx.Response(200, content=gravacao_bytes("buscape_busca.html")))
    simulador.get(re.compile(r"https://www\.buscape\.com\.br/(?!busca/).+")).mock(
        httpx.Response(503)
    )
    ofertas = await FonteBuscape(http, config).buscar(contexto("air fryer mondial"))
    assert ofertas and all(o.id.startswith("buscape:product") for o in ofertas)


async def teste_frase_sem_pagina_de_busca_tenta_menos_palavras(simulador, http, config):
    tentativas = []

    def responder(requisicao):
        tentativas.append(requisicao.url.path)
        if requisicao.url.path == "/busca/geladeira+frost":
            return httpx.Response(200, content=gravacao_bytes("buscape_busca.html"))
        return httpx.Response(404)

    simulador.get(BUSCA).mock(side_effect=responder)
    simulador.get(re.compile(r"https://www\.buscape\.com\.br/(?!busca/).+")).mock(
        httpx.Response(404)
    )
    await FonteBuscape(http, config).buscar(contexto("geladeira frost free"))
    assert tentativas == ["/busca/geladeira+frost+free", "/busca/geladeira+frost"]


async def teste_busca_exata_que_abre_a_pagina_do_produto_traz_as_lojas_dela(
    simulador, http, config
):
    # caso real: "iphone 15 128gb" leva direto à página do produto, sem lista de resultados
    busca = simulador.get(BUSCA).mock(httpx.Response(302, headers={"Location": PRODUTO}))
    produto = simulador.get(PRODUTO).mock(
        httpx.Response(200, content=gravacao_bytes("buscape_produto.html"))
    )
    ofertas = await FonteBuscape(http, config).buscar(contexto("air fryer mondial afn 40 fb"))
    assert busca.call_count == 1 and produto.call_count == 1
    assert {o.loja.nome for o in ofertas} == {"Amazon", "Magazine Luiza"}
    assert all(o.link == PRODUTO and o.relevancia >= 70 for o in ofertas)


async def teste_nenhuma_pagina_de_busca_devolve_vazio(simulador, http, config):
    rota = simulador.get(BUSCA).mock(httpx.Response(404))
    ofertas = await FonteBuscape(http, config).buscar(
        contexto("produto inexistente qualquer coisa")
    )
    assert ofertas == [] and rota.call_count == 3


async def teste_poucos_resultados_fortes_tentam_o_nucleo_da_busca(http, config, monkeypatch):
    pedidas = []

    async def resultados(self, texto):
        pedidas.append(texto)
        if texto == "multy 4 prateleiras menta":
            return [
                {
                    "name": "Estante para Livros Multy 4 Prateleiras Menta - Pnr Móveis",
                    "url": "/p/pnr",
                    "bestOffer": {"merchantName": "Magazine Luiza"},
                    "price": 261.9,
                    "storeCount": 1,
                }
            ]
        return [
            {
                "name": "Estante Escada para Livros com 4 Prateleiras Madesa",
                "url": "/p/madesa",
                "bestOffer": {"merchantName": "Americanas"},
                "price": 220.0,
                "storeCount": 1,
            }
        ]

    monkeypatch.setattr(FonteBuscape, "_resultados", resultados)
    ofertas = await FonteBuscape(http, config, lojas_diretas=[]).buscar(
        contexto("estante para livros multy 4 prateleiras menta", None)
    )
    assert pedidas[1:] == ["multy 4 prateleiras menta"]
    assert any("Pnr" in o.titulo and o.relevancia >= 95 for o in ofertas)


async def teste_oferta_da_pagina_usa_o_nome_do_produto(http, config, monkeypatch):
    # caso real: na página da BRO85MB do Buscapé, a Fast Shop não repete a capacidade no título
    produto = "Geladeira Brastemp Frost Free French Door Inverse 559 L BRO85MB"
    da_colombo = "Geladeira Brastemp Frost Free French Door 559 Litros BRO85MB Branca"

    async def resultados(self, texto):
        return [
            {
                "name": produto,
                "url": "/geladeira/bro85mb",
                "objectId": "1",
                "bestOffer": {"merchantName": "Fast Shop"},
                "price": 5299.0,
                "storeCount": 2,
            }
        ]

    async def ler_produto(self, caminho):
        return [
            {
                "id": 1,
                "sellerName": "Fast Shop",
                "price": 5299.0,
                "name": "Geladeira Frost Free French Door 3 Portas Branca Brastemp - BRO85MB",
            },
            {"id": 2, "sellerName": "Colombo", "price": 5399.0, "name": da_colombo},
        ]

    monkeypatch.setattr(FonteBuscape, "_resultados", resultados)
    monkeypatch.setattr(FonteBuscape, "_ler_produto", ler_produto)
    ofertas = await FonteBuscape(http, config).buscar(contexto("geladeira frost free 559l", None))
    por_loja = {o.loja.nome: o for o in ofertas}
    assert por_loja["Fast Shop"].titulo == produto
    assert por_loja["Fast Shop"].relevancia >= 90
    # quando o título do lojista casa tão bem quanto, ele fica
    assert por_loja["Colombo"].titulo == da_colombo


async def teste_loja_fora_do_cadastro_medido_continua_pelo_buscape(http, config):
    from app.fontes import criar_fontes

    [buscape] = [f for f in criar_fontes(http, config, ids_vtex={"carrefour"}) if f.id == "buscape"]
    assert buscape._direta("Carrefour")
    assert not buscape._direta("Fast Shop")
