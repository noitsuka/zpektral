import re
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from app.cambio import ServicoCambio
from app.cliente_http import ErroExterno
from app.fontes.ebay import FonteEbay, condicao_ebay, frete_para_o_brasil
from app.importacao import estimar_importacao
from app.modelos import Condicao, Origem, StatusFrete
from testes.conftest import contexto, resposta_json

TOKEN = "https://api.ebay.com/identity/v1/oauth2/token"
BUSCA = re.compile(r"https://api\.ebay\.com/buy/browse/v1/item_summary/search.*")
PTAX = re.compile(r"https://olinda\.bcb\.gov\.br/.*")

RESULTADOS = {
    "total": 3,
    "itemSummaries": [
        {
            "itemId": "v1|1001|0",
            "title": "AMD Radeon RX 5600 XT 6GB GDDR6 Graphics Card",
            "price": {"value": "100.00", "currency": "USD"},
            "condition": "Used",
            "image": {"imageUrl": "https://i.ebayimg.com/images/g/a/s-l225.jpg"},
            "itemWebUrl": "https://www.ebay.com/itm/1001",
            "seller": {"username": "gpu_store"},
            "shippingOptions": [
                {
                    "shippingCostType": "FIXED",
                    "shippingCost": {"value": "35.00", "currency": "USD"},
                },
                {
                    "shippingCostType": "FIXED",
                    "shippingCost": {"value": "20.00", "currency": "USD"},
                },
            ],
        },
        {
            "itemId": "v1|1002|0",
            "title": "Sapphire Pulse RX 5600 XT 6GB",
            "price": {"value": "149.99", "currency": "USD"},
            "condition": "Certified - Refurbished",
            "itemWebUrl": "https://www.ebay.com/itm/1002",
            "seller": {"username": "refurb_hub"},
        },
        {
            "itemId": "v1|1003|0",
            "title": "Preço em libras",
            "price": {"value": "90.00", "currency": "GBP"},
            "itemWebUrl": "https://www.ebay.com/itm/1003",
        },
    ],
}

PTAX_RESPOSTA = {
    "value": [
        {"cotacaoVenda": 5.4, "dataHoraCotacao": "2026-10-23 13:07:14.754"},
        {"cotacaoVenda": 5.5, "dataHoraCotacao": "2026-10-26 13:09:51.106"},
    ]
}


def habilitar(config):
    config.ebay_id_cliente = "app-id"
    config.ebay_segredo = SecretStr("segredo")
    return config


@pytest.fixture
def ebay(simulador):
    token = simulador.post(TOKEN).mock(
        resposta_json(
            {"access_token": "t1", "expires_in": 7200, "token_type": "Application Access Token"}
        )
    )
    busca = simulador.get(BUSCA).mock(resposta_json(RESULTADOS))
    ptax = simulador.get(PTAX).mock(resposta_json(PTAX_RESPOSTA))
    return token, busca, ptax


def teste_imposto_de_importacao_e_icms_por_dentro():
    produto, frete, importacao = estimar_importacao(10_000, 2_000, 5.5, 0.6, 0.2)
    assert (produto, frete) == (55_000, 11_000)
    assert importacao.imposto_importacao == 39_600
    assert importacao.icms == 26_400
    assert produto + frete + importacao.impostos == 132_000


def teste_sem_frete_os_impostos_valem_so_sobre_o_produto():
    produto, frete, importacao = estimar_importacao(10_000, None, 5.0, 0.6, 0.2)
    assert produto == 50_000
    assert frete is None
    assert importacao.imposto_importacao == 30_000
    assert importacao.icms == 20_000


def teste_condicao_e_frete_lidos_do_ebay():
    assert condicao_ebay("New") is Condicao.NOVO
    assert condicao_ebay("Used") is Condicao.USADO
    assert condicao_ebay("Seller refurbished") is Condicao.RECONDICIONADO
    assert condicao_ebay("For parts or not working") is Condicao.USADO
    assert condicao_ebay(None) is None
    assert frete_para_o_brasil(RESULTADOS["itemSummaries"][0]) == 2_000
    assert frete_para_o_brasil({"shippingOptions": [{"shippingCost": {"value": "9"}}]}) is None


async def teste_desativado_sem_credenciais(http, config):
    assert FonteEbay(http, config, ServicoCambio(http)).ativa is False


async def teste_ofertas_importadas_com_total_estimado(ebay, http, config):
    habilitar(config)
    ofertas = await FonteEbay(http, config, ServicoCambio(http)).buscar(
        contexto("rx 5600", "30130010")
    )
    assert [o.id for o in ofertas] == ["ebay:v1|1001|0", "ebay:v1|1002|0"]
    usada, recondicionada = ofertas
    assert usada.origem is Origem.IMPORTADO
    assert usada.condicao is Condicao.USADO and recondicionada.condicao is Condicao.RECONDICIONADO
    assert usada.frete.status is StatusFrete.ESTIMADO and usada.frete.valor == 11_000
    assert usada.importacao.cotacao_dolar == 5.5
    assert usada.total == 55_000 + 11_000 + usada.importacao.impostos
    assert usada.total_exato is False
    assert recondicionada.frete.status is StatusFrete.NAO_INFORMADO


async def teste_busca_pede_entrega_no_brasil_e_reaproveita_o_token(ebay, http, config):
    token, busca, _ = ebay
    habilitar(config)
    fonte = FonteEbay(http, config, ServicoCambio(http))
    await fonte.buscar(contexto("rx 5600", "30130010"))
    await fonte.buscar(contexto("rx 5600", "30130010"))
    assert token.call_count == 1
    pedido = busca.calls[-1].request
    assert "deliveryCountry:BR" in str(pedido.url)
    assert pedido.headers["x-ebay-c-marketplace-id"] == "EBAY_US"
    assert "country%3DBR%2Czip%3D30130010" in pedido.headers["x-ebay-c-enduserctx"]
    assert pedido.headers["authorization"] == "Bearer t1"


async def teste_cotacao_indisponivel_derruba_so_o_ebay(simulador, http, config):
    habilitar(config)
    simulador.post(TOKEN).mock(resposta_json({"access_token": "t1", "expires_in": 7200}))
    simulador.get(PTAX).mock(resposta_json({"value": []}))
    with pytest.raises(ErroExterno):
        await FonteEbay(http, config, ServicoCambio(http)).buscar(contexto("rx 5600"))


async def teste_cotacao_usa_o_boletim_mais_recente(simulador, http):
    rota = simulador.get(PTAX).mock(resposta_json(PTAX_RESPOSTA))
    relogio = lambda: datetime(2026, 10, 26, tzinfo=UTC)  # noqa: E731
    cambio = ServicoCambio(http, relogio=relogio)
    assert await cambio.dolar() == 5.5
    assert await cambio.dolar() == 5.5
    assert rota.call_count == 1
    assert "10-26-2026" in str(rota.calls[0].request.url)
