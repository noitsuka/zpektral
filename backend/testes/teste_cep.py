import asyncio

import httpx
import pytest

from app.cep import CepInvalido, CepNaoEncontrado, ServicoCep, normalizar_cep
from app.cliente_http import ErroExterno
from testes.conftest import resposta_json

BRASILAPI = "https://brasilapi.com.br/api/cep/v2/30130010"
VIACEP = "https://viacep.com.br/ws/30130010/json/"
BRASILAPI_OK = {
    "cep": "30130010",
    "state": "MG",
    "city": "Belo Horizonte",
    "neighborhood": "Centro",
    "street": "Praça Sete de Setembro",
}
VIACEP_OK = {
    "cep": "30130-010",
    "logradouro": "Praça Sete de Setembro",
    "bairro": "Centro",
    "localidade": "Belo Horizonte",
    "uf": "MG",
}


@pytest.mark.parametrize("bruto", ["30130010", "30130-010", " 30.130-010 "])
def teste_normalizar(bruto):
    assert normalizar_cep(bruto) == "30130010"


@pytest.mark.parametrize("bruto", ["", "123", "301300100", "00000000", "abcdefgh"])
def teste_normalizar_rejeita(bruto):
    with pytest.raises(CepInvalido):
        normalizar_cep(bruto)


async def teste_primeira_resposta_vence(simulador, http):
    async def lenta(_):
        await asyncio.sleep(2)
        return resposta_json(VIACEP_OK)

    simulador.get(BRASILAPI).mock(resposta_json(BRASILAPI_OK))
    simulador.get(VIACEP).mock(side_effect=lenta)
    laco = asyncio.get_running_loop()
    inicio = laco.time()
    endereco = await ServicoCep(http, 60, 10).consultar("30130-010")
    assert laco.time() - inicio < 1
    assert (endereco.cidade, endereco.uf, endereco.bairro) == ("Belo Horizonte", "MG", "Centro")


async def teste_recorre_ao_outro_quando_um_provedor_cai_ou_esta_desatualizado(simulador, http):
    simulador.get(BRASILAPI).mock(httpx.Response(404, json={"message": "not found"}))
    simulador.get(VIACEP).mock(resposta_json(VIACEP_OK))
    endereco = await ServicoCep(http, 60, 10).consultar("30130010")
    assert endereco.logradouro == "Praça Sete de Setembro"

    simulador.get(BRASILAPI).mock(httpx.Response(502))
    endereco = await ServicoCep(http, 60, 10).consultar("30130010")
    assert endereco.cidade == "Belo Horizonte"


async def teste_inexistente_so_quando_todos_os_provedores_concordam(simulador, http):
    simulador.get(BRASILAPI).mock(httpx.Response(404))
    simulador.get(VIACEP).mock(resposta_json({"erro": "true"}))
    servico = ServicoCep(http, 60, 10)
    with pytest.raises(CepNaoEncontrado):
        await servico.consultar("30130010")
    simulador.get(VIACEP).mock(resposta_json(VIACEP_OK))
    with pytest.raises(CepNaoEncontrado):
        await servico.consultar("30130010")


async def teste_queda_nao_vira_cep_inexistente(simulador, http):
    simulador.get(BRASILAPI).mock(httpx.Response(503))
    simulador.get(VIACEP).mock(httpx.Response(503))
    servico = ServicoCep(http, 60, 10)
    with pytest.raises(ErroExterno) as erro:
        await servico.consultar("30130010")
    assert "brasilapi.com.br: HTTP 503" in str(erro.value)
    assert "viacep.com.br: HTTP 503" in str(erro.value)
    assert isinstance(erro.value.__cause__, ErroExterno)
    endereco = await servico.resolver("30130-010")
    assert endereco.cep == "30130010" and endereco.cidade is None


async def teste_resultados_ficam_em_cache(simulador, http):
    rota = simulador.get(BRASILAPI).mock(resposta_json(BRASILAPI_OK))
    simulador.get(VIACEP).mock(resposta_json(VIACEP_OK))
    servico = ServicoCep(http, 60, 10)
    for _ in range(5):
        await servico.consultar("30130010")
    assert rota.call_count <= 1


async def teste_resposta_malformada_recorre_ao_outro_provedor(simulador, http):
    simulador.get(BRASILAPI).mock(httpx.Response(200, content=b"<html>manutencao</html>"))
    simulador.get(VIACEP).mock(resposta_json(VIACEP_OK))
    endereco = await ServicoCep(http, 60, 10).consultar("30130010")
    assert endereco.cidade == "Belo Horizonte"


async def teste_formato_inesperado_nao_vira_erro_interno(simulador, http):
    simulador.get(BRASILAPI).mock(resposta_json(["nao", "e", "objeto"]))
    simulador.get(VIACEP).mock(resposta_json("texto"))
    with pytest.raises(ErroExterno):
        await ServicoCep(http, 60, 10).consultar("30130010")


async def teste_campos_do_provedor_sao_saneados(simulador, http):
    simulador.get(BRASILAPI).mock(
        resposta_json({"street": "  Rua A  ", "neighborhood": 42, "city": "x" * 500, "state": ""})
    )
    simulador.get(VIACEP).mock(httpx.Response(502))
    endereco = await ServicoCep(http, 60, 10).consultar("30130010")
    assert endereco.logradouro == "Rua A"
    assert endereco.bairro is None
    assert len(endereco.cidade) == 120
    assert endereco.uf is None
