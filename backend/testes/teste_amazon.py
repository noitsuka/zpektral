import re

import httpx
import pytest

from app.cliente_http import ErroExterno
from app.fontes.amazon import FonteAmazon, ler_resultados, url_de_busca
from app.modelos import Origem, StatusFrete
from testes.conftest import contexto, gravacao_bytes

BUSCA = re.compile(r"https://www\.amazon\.com\.br/s\?k=.*")
PROIBIDAS = re.compile(
    r"https://www\.amazon\.com\.br/(gp/cart|gp/product/product-availability|-/).*"
)
VERIFICACAO = (
    b'<html><body><form method="get" action="/errors/validateCaptcha">'
    b"<p>Digite os caracteres que voc\xc3\xaa v\xc3\xaa abaixo</p></form></body></html>"
)


@pytest.fixture
def amazon(simulador):
    proibidas = simulador.get(PROIBIDAS).mock(httpx.Response(500))
    busca = simulador.get(BUSCA).mock(
        httpx.Response(200, content=gravacao_bytes("amazon_busca.html"))
    )
    return proibidas, busca


def teste_busca_usa_a_pagina_publica_permitida():
    assert url_de_busca("iphone 15") == "https://www.amazon.com.br/s?k=iphone+15"
    assert url_de_busca("café & leite") == "https://www.amazon.com.br/s?k=caf%C3%A9+%26+leite"


def teste_le_cada_resultado_uma_vez_por_asin():
    resultados = ler_resultados(gravacao_bytes("amazon_busca.html"))
    asins = [r.asin for r in resultados]
    assert len(asins) == len(set(asins)) == 7
    primeiro = next(r for r in resultados if r.asin == "B0CP6CVJSG")
    assert primeiro.titulo.startswith("Apple iPhone 15 (128 GB)")
    assert primeiro.titulo.endswith("Preto")
    assert primeiro.preco == 377910
    assert primeiro.preco_original == 599900
    assert primeiro.imagem and primeiro.imagem.startswith("https://m.media-amazon.com/")
    assert primeiro.parcelas == 12 and primeiro.valor_parcela
    assert not any(r.titulo.startswith("Anúncio patrocinado") for r in resultados)


def teste_frete_gratis_so_no_primeiro_pedido_nao_conta_como_gratis():
    resultados = ler_resultados(gravacao_bytes("amazon_busca.html"))
    assert all(not r.frete_gratis for r in resultados)
    assert all("primeiro pedido" in (r.entrega or "") for r in resultados)


def teste_pagina_de_verificacao_e_erro_e_nao_e_contornada():
    with pytest.raises(ErroExterno, match="verificação"):
        ler_resultados(VERIFICACAO)


async def teste_monta_ofertas_sem_inventar_frete(amazon, http, config):
    proibidas, busca = amazon
    ofertas = await FonteAmazon(http, config).buscar(contexto("iphone 15"))
    assert busca.call_count == 1
    assert not proibidas.called
    assert ofertas
    for o in ofertas:
        assert o.loja.id == "amazon"
        assert o.origem is Origem.MARKETPLACE
        assert o.link.startswith("https://www.amazon.com.br/dp/")
        assert o.frete.status is StatusFrete.NAO_INFORMADO
        assert o.total_exato is False
    parcelada = next(o for o in ofertas if o.id == "amazon:B0CP6CVJSG")
    assert parcelada.parcelamento and parcelada.parcelamento.parcelas == 12


async def teste_verificacao_vira_falha_da_fonte(simulador, http, config):
    simulador.get(BUSCA).mock(httpx.Response(200, content=VERIFICACAO))
    with pytest.raises(ErroExterno):
        await FonteAmazon(http, config).buscar(contexto("iphone 15"))


async def teste_503_da_amazon_vira_falha_sem_insistir(simulador, http, config):
    rota = simulador.get(BUSCA).mock(httpx.Response(503, content=VERIFICACAO))
    with pytest.raises(ErroExterno):
        await FonteAmazon(http, config).buscar(contexto("iphone 15"))
    assert rota.call_count == 1


class FreteFalso:
    def __init__(self, resultados=None, erro=None):
        self.resultados = resultados or {}
        self.erro = erro
        self.pedidos = []

    async def cotar(self, asins, cep, destino):
        self.pedidos.append((list(asins), cep))
        if self.erro:
            raise self.erro
        destino.update(self.resultados)


async def teste_frete_por_navegador_entra_na_oferta(amazon, http, config):
    from app.navegador.base import CotacaoNavegador, StatusCotacao

    config.navegador_cotacoes = 3
    por_ordem = [
        CotacaoNavegador(StatusCotacao.COTADO, valor=1990, prazo_dias=3),
        CotacaoNavegador(StatusCotacao.INDISPONIVEL),
        CotacaoNavegador(StatusCotacao.NAO_ENTREGA),
    ]

    class FretePorOrdem(FreteFalso):
        async def cotar(self, asins, cep, destino):
            self.pedidos.append((list(asins), cep))
            destino.update(dict(zip(asins, por_ordem, strict=True)))

    frete = FretePorOrdem()
    estados = []
    ofertas = await FonteAmazon(http, config, frete=frete).buscar(
        contexto("iphone 15", cep="01310100"),
        lambda lote: estados.append({o.id: o.frete.status for o in lote}),
    )
    [(asins, cep)] = frete.pedidos
    assert cep == "01310100" and len(asins) == 3
    por_id = {o.id: o for o in ofertas}
    cotada, sem_estoque, sem_entrega = (por_id[f"amazon:{a}"] for a in asins)
    assert cotada.frete.status is StatusFrete.CALCULADO and cotada.frete.valor == 1990
    assert cotada.total == cotada.preco + 1990 and cotada.total_exato
    assert sem_estoque.disponivel is False
    assert sem_entrega.frete.status is StatusFrete.NAO_ENTREGA
    assert estados == [
        {
            o.id: StatusFrete.CALCULANDO
            if o.id.split(":")[1] in asins
            else StatusFrete.NAO_INFORMADO
            for o in ofertas
        }
    ]


async def teste_navegador_indisponivel_mantem_a_busca(amazon, http, config):
    from app.navegador.base import NavegadorIndisponivel

    frete = FreteFalso(erro=NavegadorIndisponivel("pacote playwright não instalado"))
    ofertas = await FonteAmazon(http, config, frete=frete).buscar(contexto("iphone 15"))
    assert ofertas and frete.pedidos
    assert all(o.frete.status is StatusFrete.NAO_INFORMADO for o in ofertas)


async def teste_sem_cep_nao_abre_navegador(amazon, http, config):
    frete = FreteFalso()
    ofertas = await FonteAmazon(http, config, frete=frete).buscar(contexto("iphone 15", cep=None))
    assert ofertas and frete.pedidos == []
