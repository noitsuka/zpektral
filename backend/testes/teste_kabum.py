import copy
import re

import httpx
import pytest

from app.fontes.kabum import FonteKabum, _parcelamento
from app.modelos import Origem, StatusFrete
from testes.conftest import contexto, gravacao_json, resposta_json

API = re.compile(r"https://servicespub\.prod\.api\.aws\.grupokabum\.com\.br/catalog/v2/products.*")


def entrada(**atributos):
    base = copy.deepcopy(gravacao_json("kabum.json")["data"][0])
    base["attributes"].update(atributos)
    return base


async def executar(simulador, http, config, entradas, agora=1_792_500_000, cep="30130010"):
    simulador.get(API).mock(resposta_json({"data": entradas}))
    fonte = FonteKabum(http, config, relogio=lambda: agora)
    return await fonte.buscar(contexto("rtx 4060", cep))


async def teste_le_resposta_real(simulador, http, config):
    dados = gravacao_json("kabum.json")["data"]
    ofertas = await executar(simulador, http, config, dados)
    assert len(ofertas) == sum(1 for e in dados if e["attributes"]["available"])
    for o in ofertas:
        assert o.link.startswith("https://www.kabum.com.br/produto/")
        assert o.preco > 0 and o.preco_pix is not None and o.preco_pix <= o.preco
        assert o.loja.id == "kabum"


async def teste_preco_de_campanha_ativa_prevalece(simulador, http, config):
    e = entrada(
        price=9999.0,
        price_with_discount=8999.1,
        offer={"price": 8399.0, "price_with_discount": 7559.1, "starts_at": 100, "ends_at": 200},
    )
    [o] = await executar(simulador, http, config, [e], agora=150)
    assert (o.preco, o.preco_pix) == (839900, 755910)
    assert o.melhor_preco == 755910


async def teste_campanha_expirada_e_ignorada(simulador, http, config):
    e = entrada(
        price=9999.0,
        price_with_discount=8999.1,
        offer={"price": 8399.0, "price_with_discount": 7559.1, "starts_at": 100, "ends_at": 200},
    )
    [o] = await executar(simulador, http, config, [e], agora=201)
    assert (o.preco, o.preco_pix) == (999900, 899910)


async def teste_frete_gratis_e_anunciado_e_nao_cotado(simulador, http, config):
    [o] = await executar(simulador, http, config, [entrada(has_free_shipping=True)])
    assert o.frete.status is StatusFrete.GRATIS_ANUNCIADO
    assert o.frete.valor == 0
    assert o.total_exato is False


async def teste_frete_pago_fica_nao_informado(simulador, http, config):
    [o] = await executar(simulador, http, config, [entrada(has_free_shipping=False)])
    assert o.frete.status is StatusFrete.NAO_INFORMADO
    [o] = await executar(simulador, http, config, [entrada(has_free_shipping=False)], cep=None)
    assert o.frete.status is StatusFrete.SEM_CEP


async def teste_produtos_indisponiveis_sao_pulados(simulador, http, config):
    assert await executar(simulador, http, config, [entrada(available=False)]) == []
    assert await executar(simulador, http, config, [entrada(price=0)]) == []


async def teste_vendedor_de_marketplace(simulador, http, config):
    e = entrada(is_marketplace=True, marketplace={"seller_name": "Acer"})
    [o] = await executar(simulador, http, config, [e])
    assert o.origem is Origem.MARKETPLACE and o.vendedor == "Acer"
    e = entrada(is_marketplace=False)
    [o] = await executar(simulador, http, config, [e])
    assert o.origem is Origem.LOJA and o.vendedor == "KaBuM!"


async def teste_erro_da_api_e_propagado(simulador, http, config):
    from app.cliente_http import ErroExterno

    simulador.get(API).mock(httpx.Response(403))
    with pytest.raises(ErroExterno):
        await FonteKabum(http, config).buscar(contexto("rtx 4060"))


@pytest.mark.parametrize(
    ("texto", "cartao", "esperadas"),
    [
        ("10x de R$ 839,90", 839900, (10, 83990, 839900, False)),
        ("10x de R$ 1513,78", 1513789, (10, 151378, 1513789, False)),
        ("12x de R$ 100,00", 100000, (12, 10000, 120000, True)),
        (None, 100, None),
        ("à vista", 100, None),
    ],
)
def teste_texto_de_parcelamento(texto, cartao, esperadas):
    resultado = _parcelamento(texto, cartao)
    if esperadas is None:
        assert resultado is None
    else:
        assert (resultado.parcelas, resultado.valor, resultado.total, resultado.juros) == esperadas
