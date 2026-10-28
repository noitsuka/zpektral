import asyncio
import json
import re
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from app.fontes.mercadolivre import CofreTokens, FonteMercadoLivre
from app.modelos import StatusFrete
from testes.conftest import contexto, resposta_json

URL_TOKEN = "https://api.mercadolibre.com/oauth/token"
BUSCA_ML = re.compile(r"https://api\.mercadolibre\.com/sites/MLB/search.*")
FRETE_ML = re.compile(r"https://api\.mercadolibre\.com/items/(MLB\d+)/shipping_options.*")

RESULTADOS = {
    "results": [
        {
            "id": "MLB1",
            "title": "Placa de Vídeo RTX 4060 8GB",
            "price": 1899.9,
            "original_price": 2199,
            "permalink": "https://produto.mercadolivre.com.br/MLB-1",
            "thumbnail": "http://http2.mlstatic.com/D_1.jpg",
            "condition": "new",
            "shipping": {"free_shipping": False},
            "seller": {"nickname": "LOJA_X"},
            "installments": {"quantity": 10, "amount": 189.99, "rate": 0},
        },
        {
            "id": "MLB2",
            "title": "Placa de Vídeo RTX 4060 Usada",
            "price": 1500,
            "permalink": "https://produto.mercadolivre.com.br/MLB-2",
            "condition": "used",
            "shipping": {"free_shipping": True},
            "official_store_name": "Loja Oficial",
            "installments": {"quantity": 12, "amount": 150.5, "rate": 19.9},
        },
        {"id": "MLB3", "title": "Sem preço", "price": None},
    ]
}


def configurado(config, tmp_path):
    config.ml_id_cliente = "id"
    config.ml_segredo_cliente = SecretStr("secret")
    config.ml_token_renovacao = SecretStr("r1")
    config.ml_arquivo_token = str(tmp_path / "token.json")
    return config


def rota_token(simulador, tokens_renovacao: list[str]):
    chamadas = iter(range(100))

    def responder(requisicao: httpx.Request):
        formulario = parse_qs(requisicao.content.decode())
        tokens_renovacao.append(formulario["refresh_token"][0])
        n = next(chamadas)
        return resposta_json(
            {"access_token": f"a{n}", "refresh_token": f"r{n + 2}", "expires_in": 21600}
        )

    return simulador.post(URL_TOKEN).mock(side_effect=responder)


async def teste_desativada_sem_credenciais(http, config):
    assert FonteMercadoLivre(http, config).ativa is False


async def teste_renovacao_de_token_roda_e_persiste(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    loja = CofreTokens(http, config, relogio=lambda: agora[0])

    assert await loja.obter_token() == "a0"
    assert await loja.obter_token() == "a0"
    salvo = json.loads((tmp_path / "token.json").read_text())
    assert salvo["refresh_token"] == "r2"

    agora[0] += 21600
    assert await loja.obter_token() == "a1"
    assert usados == ["r1", "r2"]

    reiniciado = CofreTokens(http, config, relogio=lambda: agora[0] + 30000)
    await reiniciado.obter_token()
    assert usados[-1] == "r3"


async def teste_requisicoes_simultaneas_renovam_uma_vez(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    usados: list[str] = []
    rota = rota_token(simulador, usados)
    loja = CofreTokens(http, config)
    emitidos = await asyncio.gather(*(loja.obter_token() for _ in range(10)))
    assert set(emitidos) == {"a0"}
    assert rota.call_count == 1


async def teste_busca_com_frete_cotado(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    rota_token(simulador, [])
    buscar = simulador.get(BUSCA_ML).mock(resposta_json(RESULTADOS))

    def frete(requisicao: httpx.Request):
        assert requisicao.headers["authorization"] == "Bearer a0"
        assert "zip_code=30130010" in str(requisicao.url)
        return resposta_json(
            {
                "options": [
                    {"name": "Normal", "cost": 25.9, "estimated_delivery_time": {}},
                    {"name": "Expresso", "cost": 39.9, "estimated_delivery_time": {}},
                ]
            }
        )

    simulador.get(FRETE_ML).mock(side_effect=frete)
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))

    assert buscar.calls[0].request.headers["authorization"] == "Bearer a0"
    por_id = {o.id: o for o in ofertas}
    assert set(por_id) == {"mercadolivre:MLB1", "mercadolivre:MLB2"}

    novo = por_id["mercadolivre:MLB1"]
    assert novo.preco == 189990 and novo.preco_original == 219900
    assert novo.frete.status is StatusFrete.CALCULADO and novo.frete.valor == 2590
    assert novo.total == 189990 + 2590 and novo.total_exato
    assert novo.imagem.startswith("https://")
    assert novo.parcelamento.parcelas == 10 and not novo.parcelamento.juros

    usados = por_id["mercadolivre:MLB2"]
    assert usados.titulo.endswith("(usado)")
    assert usados.vendedor == "Loja Oficial"
    assert usados.parcelamento.juros


async def teste_sem_opcoes_significa_sem_entrega(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_ENTREGA


async def teste_cotacao_falha_mantem_oferta(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(httpx.Response(500))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_INFORMADO
    assert oferta.preco == 189990


async def teste_token_revogado_e_renovado_uma_vez(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    usados: list[str] = []
    rota_token(simulador, usados)
    respostas = iter([httpx.Response(401), resposta_json(RESULTADOS)])
    busca = simulador.get(BUSCA_ML).mock(side_effect=lambda _: next(respostas))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert ofertas
    assert busca.call_count == 2
    assert busca.calls[-1].request.headers["authorization"] == "Bearer a1"


async def teste_resposta_de_token_sem_access_token_vira_erro_externo(
    simulador, http, config, tmp_path
):
    from app.cliente_http import ErroExterno

    configurado(config, tmp_path)
    simulador.post(URL_TOKEN).mock(resposta_json({"error": "invalid_grant"}))
    with pytest.raises(ErroExterno):
        await CofreTokens(http, config).obter_token()


def teste_arquivo_de_token_corrompido_e_ignorado(http, config, tmp_path):
    configurado(config, tmp_path)
    (tmp_path / "token.json").write_text(
        json.dumps({"refresh_token": "r9", "access_token": 5, "expires_at": "amanhã"})
    )
    cofre = CofreTokens(http, config)
    assert cofre._renovacao == "r9"
    assert cofre._acesso is None and cofre._expira == 0.0


def teste_data_de_entrega_sem_fuso_vira_prazo():
    from app.fontes.mercadolivre import _opcao

    opcao = _opcao({"cost": 10, "estimated_delivery_time": {"date": "2999-01-01T00:00:00"}})
    assert opcao.prazo_dias is not None and opcao.prazo_dias > 0


async def teste_token_expirado_no_meio_da_cotacao_e_renovado(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    usados: list[str] = []
    rota_token(simulador, usados)
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))

    def frete(requisicao: httpx.Request):
        if requisicao.headers["authorization"] == "Bearer a0":
            return httpx.Response(401)
        return resposta_json(
            {
                "options": [
                    {
                        "name": "Normal",
                        "cost": 0,
                        "estimated_delivery_time": {"date": "2099-01-05T00:00:00"},
                    }
                ]
            }
        )

    rota_frete = simulador.get(FRETE_ML).mock(side_effect=frete)
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert rota_frete.call_count == 2
    assert usados == ["r1", "r2"]
    assert oferta.frete.status is StatusFrete.CALCULADO
    assert oferta.frete.valor == 0
    assert oferta.frete.prazo_dias and oferta.frete.prazo_dias > 0
    assert oferta.total_exato


async def teste_busca_recusada_com_403_explica_o_motivo(simulador, http, config, tmp_path):
    from app.cliente_http import ErroExterno

    configurado(config, tmp_path)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(
        resposta_json({"message": "forbidden", "error": "forbidden", "status": 403}, status=403)
    )
    with pytest.raises(ErroExterno, match="403"):
        await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))


async def teste_frete_gratis_anunciado_sem_cep(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][1:2]}))
    frete = simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060 usada", cep=None))
    assert not frete.called
    assert oferta.frete.status is StatusFrete.GRATIS_ANUNCIADO and oferta.frete.valor == 0
    assert oferta.vendedor == "Loja Oficial"


async def teste_vendedor_pelo_apelido(simulador, http, config, tmp_path):
    configurado(config, tmp_path)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert oferta.vendedor == "LOJA_X"


@pytest.mark.skip(
    reason="credentials missing: ML_ID_CLIENTE, ML_SEGREDO_CLIENTE, ML_TOKEN_RENOVACAO"
)
async def teste_ao_vivo_mercado_livre(http, config):
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("iphone 15", "01310100"))
    assert ofertas
