import json

import httpx
import pytest

from scripts.sondar_lojas_vtex import CAMINHOS, executar, proibido_pelo_robots

INTELIGENTE, LEGADA, SIMULACAO = CAMINHOS
LOJA = {"id": "x", "nome": "X", "dominio": "www.x.com.br", "segmento": "casa"}
BASE = "https://www.x.com.br"


def vendedor(id_vendedor: str, estoque: int) -> dict:
    return {"sellerId": id_vendedor, "commertialOffer": {"AvailableQuantity": estoque}}


PRODUTO = {"items": [{"itemId": "1", "sellers": [vendedor("1", 0), vendedor("2", 5)]}]}
FRETE = {"logisticsInfo": [{"slas": [{"id": "Normal", "price": 990}]}]}


@pytest.mark.parametrize(
    ("robots", "proibidos"),
    [
        ("User-agent: *\nDisallow: /api/", [INTELIGENTE, LEGADA, SIMULACAO]),
        ("User-agent: *\nDisallow: /*ft=*", [LEGADA]),
        ("User-agent: *\nDisallow: /*?ft=*", [LEGADA]),
        ("User-agent: *\nAllow: /\nDisallow: /*order*", [SIMULACAO]),
        ("User-agent: *\nDisallow: /*page=*", [INTELIGENTE]),
        ("User-agent: *\nDisallow: /api/\nAllow: /api/io/", [LEGADA, SIMULACAO]),
        ("User-agent: *\nDisallow: /api/checkout/pub/orderForms/simulation$", [SIMULACAO]),
        ("User-agent: *\nDisallow: /api/checkout/pub/orderForms$", []),
        ("User-agent: Googlebot\nUser-agent: *\nDisallow: /api/", [INTELIGENTE, LEGADA, SIMULACAO]),
        ("User-agent: *\nUser-agent: Googlebot\nDisallow: /api/", [INTELIGENTE, LEGADA, SIMULACAO]),
        ("User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nDisallow: /checkout/", []),
        ("User-agent: *\nDisallow: /api/\n\nUser-agent: Zpektral\nAllow: /", []),
        ("Disallow: /api/\nUser-agent: *\nDisallow:", []),
        ("User-agent: *\nDisallow: /busca/*  # páginas de busca", []),
    ],
)
def teste_robots_segue_a_rfc_9309(robots, proibidos):
    assert proibido_pelo_robots(robots) == proibidos


async def _sondar(simulador, robots: httpx.Response) -> tuple:
    simulador.get(f"{BASE}/robots.txt").mock(robots)
    inteligente = simulador.get(url__startswith=f"{BASE}{INTELIGENTE}").mock(
        httpx.Response(200, json={"products": [PRODUTO]})
    )
    legada = simulador.get(url__startswith=f"{BASE}{LEGADA}").mock(
        httpx.Response(200, json=[PRODUTO])
    )
    simulacao = simulador.post(f"{BASE}{SIMULACAO}").mock(httpx.Response(200, json=FRETE))
    [resultado] = await executar([LOJA], "01310100", 1)
    return resultado, inteligente, legada, simulacao


async def teste_simula_o_vendedor_que_tem_estoque(simulador):
    resultado, _, _, simulacao = await _sondar(simulador, httpx.Response(404))
    [chamada] = simulacao.calls
    assert json.loads(chamada.request.content)["items"][0]["seller"] == "2"
    assert resultado.aprovada


async def teste_tenta_outro_termo_quando_nada_tem_estoque(simulador):
    sem_estoque = {"items": [{"itemId": "9", "sellers": [vendedor("1", 0)]}]}
    simulador.get(f"{BASE}/robots.txt").mock(httpx.Response(404))
    inteligente = simulador.get(url__startswith=f"{BASE}{INTELIGENTE}").mock(
        side_effect=[
            httpx.Response(200, json={"products": [sem_estoque]}),
            httpx.Response(200, json={"products": [PRODUTO]}),
        ]
    )
    simulador.post(f"{BASE}{SIMULACAO}").mock(httpx.Response(200, json=FRETE))
    [resultado] = await executar([LOJA], "01310100", 1)
    assert resultado.aprovada and inteligente.call_count == 2


async def teste_simula_no_canal_de_vendas_da_loja_e_mostra_o_motivo(simulador):
    simulador.get(f"{BASE}/robots.txt").mock(httpx.Response(404))
    simulador.get(url__startswith=f"{BASE}{INTELIGENTE}").mock(
        httpx.Response(200, json={"products": [PRODUTO]})
    )
    simulacao = simulador.post(f"{BASE}{SIMULACAO}").mock(
        httpx.Response(200, json={"messages": [{"code": "ORD027"}]})
    )
    [resultado] = await executar([{**LOJA, "sc": 2}], "01310100", 1)
    assert simulacao.calls.last.request.url.params["sc"] == "2"
    assert not resultado.aprovada and "simulação: ORD027" in resultado.erros


async def teste_cookie_com_acento_nao_derruba_a_sondagem(simulador):
    robots = httpx.Response(
        200,
        text="User-agent: *\nDisallow:",
        headers=[(b"set-cookie", "regionName=Ceará; Path=/".encode())],
    )
    resultado, *_ = await _sondar(simulador, robots)
    assert resultado.aprovada and resultado.busca == "auto"
    assert resultado.erros == []


async def teste_sondagem_nao_pede_a_busca_que_o_robots_proibe(simulador):
    robots = httpx.Response(200, text="User-agent: *\nDisallow: /*ft=*")
    resultado, _, legada, _ = await _sondar(simulador, robots)
    assert resultado.aprovada and resultado.busca == "is"
    assert not legada.called


async def teste_robots_que_proibe_o_frete_reprova_sem_buscar(simulador):
    robots = httpx.Response(200, text="User-agent: *\nDisallow: */checkout*")
    resultado, inteligente, legada, _ = await _sondar(simulador, robots)
    assert not resultado.aprovada
    assert not inteligente.called and not legada.called


async def teste_robots_fora_do_ar_conta_como_proibido(simulador):
    resultado, inteligente, *_ = await _sondar(simulador, httpx.Response(503))
    assert not resultado.aprovada and resultado.robots == "HTTP 503"
    assert not inteligente.called
