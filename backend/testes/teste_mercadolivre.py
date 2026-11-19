import asyncio
import logging
import os
import re
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from app.banco import Base, criar_motor, criar_sessoes
from app.cliente_http import ErroExterno
from app.credenciais import Cifra, GuardaCredenciais, nova_chave
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


def configurado(config):
    config.ml_id_cliente = "id"
    config.ml_segredo_cliente = SecretStr("segredo-do-cliente")
    config.ml_token_renovacao = SecretStr("r1")
    return config


@pytest.fixture
async def guarda(tmp_path):
    motor = criar_motor(f"sqlite+aiosqlite:///{tmp_path / 'credenciais.db'}")
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)
    yield GuardaCredenciais(criar_sessoes(motor), Cifra(nova_chave()))
    await motor.dispose()


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


async def teste_renovacao_guarda_o_token_novo_para_a_proxima_instancia(
    simulador, http, config, guarda
):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    cofre = CofreTokens(http, config, guarda, relogio=lambda: agora[0])

    assert await cofre.obter_token() == "a0"
    assert await cofre.obter_token() == "a0"
    assert (await guarda.ler("mercadolivre"))["refresh_token"] == "r2"

    agora[0] += 21600
    assert await cofre.obter_token() == "a1"
    assert usados == ["r1", "r2"]

    reiniciada = CofreTokens(http, config, guarda, relogio=lambda: agora[0] + 30000)
    assert await reiniciada.obter_token() == "a2"
    assert usados == ["r1", "r2", "r3"]


async def teste_outra_instancia_usa_o_token_valido_sem_renovar(simulador, http, config, guarda):
    configurado(config)
    rota = rota_token(simulador, [])
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    assert rota.call_count == 1


async def teste_token_recusado_pela_api_nao_volta_do_banco(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    outra = CofreTokens(http, config, guarda)
    outra.invalidar("a0")
    assert await outra.obter_token() == "a1"
    assert usados == ["r1", "r2"]


async def teste_novo_token_no_ambiente_vale_sobre_o_guardado(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    await CofreTokens(http, config, guarda, relogio=lambda: agora[0]).obter_token()

    config.ml_token_renovacao = SecretStr("reautorizado")
    agora[0] += 60
    await CofreTokens(http, config, guarda, relogio=lambda: agora[0]).obter_token()
    assert usados == ["r1", "reautorizado"]


async def teste_autorizacao_revogada_pede_reautorizacao_sem_insistir(
    simulador, http, config, guarda
):
    configurado(config)
    rota = simulador.post(URL_TOKEN).mock(
        resposta_json({"error": "invalid_grant", "message": "invalid_grant"}, status=400)
    )
    cofre = CofreTokens(http, config, guarda)
    for _ in range(2):
        with pytest.raises(ErroExterno, match="autorize de novo") as erro:
            await cofre.obter_token()
        assert erro.value.bloqueio
    assert rota.call_count == 1


async def teste_credenciais_nao_vazam_em_log_nem_em_erro(simulador, http, config, guarda, caplog):
    configurado(config)
    config.ml_token_renovacao = SecretStr("TG-renovacao-secreta")
    simulador.post(URL_TOKEN).mock(httpx.Response(500, text="erro interno"))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ErroExterno) as erro:
        await CofreTokens(http, config, guarda).obter_token()
    texto = caplog.text + str(erro.value) + repr(config)
    assert "TG-renovacao-secreta" not in texto
    assert "segredo-do-cliente" not in texto


async def teste_sem_banco_renova_e_gira_o_token_na_memoria(simulador, http, config):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    cofre = CofreTokens(http, config, relogio=lambda: agora[0])
    await cofre.obter_token()
    agora[0] += 21600
    await cofre.obter_token()
    assert usados == ["r1", "r2"]


async def teste_requisicoes_simultaneas_renovam_uma_vez(simulador, http, config, guarda):
    configurado(config)
    rota = rota_token(simulador, [])
    loja = CofreTokens(http, config, guarda)
    emitidos = await asyncio.gather(*(loja.obter_token() for _ in range(10)))
    assert set(emitidos) == {"a0"}
    assert rota.call_count == 1


async def teste_busca_com_frete_cotado(simulador, http, config):
    configurado(config)
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


async def teste_sem_opcoes_significa_sem_entrega(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_ENTREGA


async def teste_cotacao_falha_mantem_oferta(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(httpx.Response(500))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_INFORMADO
    assert oferta.preco == 189990


async def teste_token_revogado_e_renovado_uma_vez(simulador, http, config):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    respostas = iter([httpx.Response(401), resposta_json(RESULTADOS)])
    busca = simulador.get(BUSCA_ML).mock(side_effect=lambda _: next(respostas))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert ofertas
    assert busca.call_count == 2
    assert busca.calls[-1].request.headers["authorization"] == "Bearer a1"


async def teste_resposta_de_token_sem_access_token_vira_erro_externo(simulador, http, config):
    configurado(config)
    simulador.post(URL_TOKEN).mock(resposta_json({"error": "invalid_grant"}))
    with pytest.raises(ErroExterno):
        await CofreTokens(http, config).obter_token()


def teste_data_de_entrega_sem_fuso_vira_prazo():
    from app.fontes.mercadolivre import _opcao

    opcao = _opcao({"cost": 10, "estimated_delivery_time": {"date": "2999-01-01T00:00:00"}})
    assert opcao.prazo_dias is not None and opcao.prazo_dias > 0


async def teste_token_expirado_no_meio_da_cotacao_e_renovado(simulador, http, config):
    configurado(config)
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


async def teste_busca_recusada_com_403_explica_o_motivo(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(
        resposta_json({"message": "forbidden", "error": "forbidden", "status": 403}, status=403)
    )
    with pytest.raises(ErroExterno, match="403") as erro:
        await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert erro.value.bloqueio


async def teste_frete_gratis_anunciado_sem_cep(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][1:2]}))
    frete = simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060 usada", cep=None))
    assert not frete.called
    assert oferta.frete.status is StatusFrete.GRATIS_ANUNCIADO and oferta.frete.valor == 0
    assert oferta.vendedor == "Loja Oficial"


async def teste_vendedor_pelo_apelido(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(BUSCA_ML).mock(resposta_json({"results": RESULTADOS["results"][:1]}))
    simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert oferta.vendedor == "LOJA_X"


@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("ML_TOKEN_RENOVACAO"), reason="sem credenciais do Mercado Livre"
)
async def teste_ao_vivo_mercado_livre(http, config):
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("iphone 15", "01310100"))
    assert ofertas
