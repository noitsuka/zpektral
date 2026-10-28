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


async def teste_lojistas_consultados_direto_sao_pulados(buscape, http, config):
    tudo = await FonteBuscape(http, config).buscar(contexto("air fryer mondial"))
    assert "Magazine Luiza" in {o.loja.nome for o in tudo}
    filtradas = await FonteBuscape(http, config, lojas_diretas=["Magazine Luiza"]).buscar(
        contexto("air fryer mondial")
    )
    assert "Magazine Luiza" not in {o.loja.nome for o in filtradas}


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


async def teste_nenhuma_pagina_de_busca_devolve_vazio(simulador, http, config):
    rota = simulador.get(BUSCA).mock(httpx.Response(404))
    ofertas = await FonteBuscape(http, config).buscar(
        contexto("produto inexistente qualquer coisa")
    )
    assert ofertas == [] and rota.call_count == 3
