import asyncio
import random
import time
from typing import Any

import httpx
import pytest

from app.busca import ServicoBusca
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes.kabum import FonteKabum
from app.fontes.vtex import FonteVtex, aplicar_simulacao, carregar_lojas
from app.modelos import Endereco, Loja, Oferta, StatusFrete
from testes.conftest import contexto

pytestmark = pytest.mark.live

CONSULTAS = ["smart tv 55", "geladeira frost free", "air fryer", "notebook", "fralda"]
CEPS = {
    "São Paulo": "01310100",
    "Belo Horizonte": "30130010",
    "Porto Alegre": "90010000",
    "Rio Branco": "69900000",
    "Manaus": "69005000",
}
AMOSTRA_POR_RODADA = 12
DOMINIOS = {s.id: s.dominio for s in carregar_lojas()}


@pytest.fixture(scope="module")
def config_ao_vivo() -> Configuracoes:
    return Configuracoes(_env_file=None)


async def _simular(cliente: httpx.AsyncClient, oferta: Oferta, cep: str) -> dict[str, Any]:
    id_loja, sku, vendedor = oferta.id.split(":")
    corpo = {"items": [{"id": sku, "quantity": 1, "seller": vendedor}], "postalCode": cep}
    url = f"https://{DOMINIOS[id_loja]}/api/checkout/pub/orderForms/simulation"
    r = await cliente.post(url, json={**corpo, "country": "BRA"})
    r.raise_for_status()
    return r.json()


def total_independente(dados: dict[str, Any]) -> int | None:
    itens = dados.get("items") or []
    if not itens or itens[0]["availability"] != "available":
        return None
    avista_unicas = [
        i["total"]
        for opcao in dados["paymentData"]["installmentOptions"]
        if opcao["paymentGroupName"] in ("creditCardPaymentGroup", "instantPaymentPaymentGroup")
        for i in opcao["installments"]
        if i["count"] == 1
    ]
    preco = min(avista_unicas) if avista_unicas else sum(t["value"] for t in dados["totals"])
    entregas = [
        s["price"] + s.get("tax", 0)
        for s in dados["logisticsInfo"][0]["slas"]
        if s.get("deliveryChannel") != "pickup-in-point"
    ]
    return preco + min(entregas) if entregas else None


def total_app(dados: dict[str, Any]) -> int | None:
    oferta = Oferta(id="x", titulo="x", link="x", loja=Loja("x", "x"), preco=1)
    aplicar_simulacao(oferta, dados, tem_cep=True)
    oferta.consolidar()
    return oferta.total if oferta.frete.status is StatusFrete.CALCULADO else None


@pytest.mark.parametrize("consulta", CONSULTAS)
@pytest.mark.parametrize("cidade", list(CEPS))
async def teste_totais_exatos_batem_com_o_checkout_da_loja(consulta, cidade, config_ao_vivo):
    cep = CEPS[cidade]
    http = ClienteHttp(config_ao_vivo)
    fontes = [FonteVtex(s, http, config_ao_vivo) for s in carregar_lojas()]
    servico = ServicoBusca(fontes, config_ao_vivo)
    trabalho, _ = servico.iniciar(consulta, Endereco(cep, None, None, cidade, None))
    await trabalho.aguardar()

    exatas = [o for o in trabalho.ofertas if o.total_exato]
    vtex_ok = sum(r.status == "ok" for r in trabalho.relatorios)
    print(
        f"\n{consulta!r} em {cidade}: {len(trabalho.ofertas)} ofertas, "
        f"{len(exatas)} com total exato, "
        f"{vtex_ok}/{len(fontes)} lojas ok, {trabalho.tempo_decorrido_ms} ms"
    )
    assert vtex_ok >= len(fontes) * 0.8
    for o in exatas:
        assert o.frete.status is StatusFrete.CALCULADO
        assert o.total == o.melhor_preco + o.frete.valor

    amostra = random.Random(f"{consulta}{cep}").sample(exatas, min(AMOSTRA_POR_RODADA, len(exatas)))
    bruto = httpx.AsyncClient(timeout=15, headers={"user-agent": config_ao_vivo.agente_usuario})
    try:
        respostas = await asyncio.gather(*(_simular(bruto, o, cep) for o in amostra))
    finally:
        await bruto.aclose()
        await http.fechar()

    errados = [
        (o.id, total_app(dados), total_independente(dados))
        for o, dados in zip(amostra, respostas, strict=True)
        if total_app(dados) != total_independente(dados)
    ]
    assert not errados, f"cálculo divergente (id, app, independente): {errados}"

    mudaram = sum(
        1
        for o, dados in zip(amostra, respostas, strict=True)
        if (agora := total_independente(dados)) is not None and agora != o.total
    )
    print(f"   {len(amostra)} conferidas, {mudaram} mudaram na loja desde a busca")


@pytest.mark.parametrize("consulta", ["rtx 4060", "ssd 1tb", "monitor gamer"])
async def teste_precos_da_kabum_batem_com_a_api_de_produto(consulta, config_ao_vivo):
    http = ClienteHttp(config_ao_vivo)
    try:
        ofertas = await FonteKabum(http, config_ao_vivo).buscar(contexto(consulta))
        assert ofertas
        agora = time.time()
        for o in ofertas[:8]:
            id_produto = o.id.split(":")[1]
            dados = await http.obter_json(
                "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products/"
                + id_produto
            )
            atr = (dados.get("data") or dados)["attributes"]
            promocao = atr.get("offer") or {}
            ativas = promocao.get("price") and promocao["starts_at"] <= agora <= promocao["ends_at"]
            cartao = promocao["price"] if ativas else atr["price"]
            assert o.preco == round(cartao * 100), (o.id, o.preco, cartao)
    finally:
        await http.fechar()
