import httpx
import pytest

from app.cliente_http import ErroExterno, ler_json


@pytest.mark.parametrize(
    "url",
    [
        "http://loja.com.br/api",
        "https://localhost/api",
        "https://127.0.0.1/api",
        "https://10.0.0.5/api",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/api",
        "https://metadata.google.internal/x",
    ],
)
async def teste_destinos_internos_ou_sem_https_sao_recusados(simulador, http, url):
    rota = simulador.get(url).mock(httpx.Response(200, json={}))
    with pytest.raises(ErroExterno):
        await http.requisitar("GET", url)
    assert not rota.called


async def teste_redirecionamento_para_destino_interno_e_recusado(simulador, http):
    simulador.get("https://loja.com.br/api").mock(
        httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
    )
    interno = simulador.get("http://169.254.169.254/latest").mock(httpx.Response(200))
    with pytest.raises(ErroExterno):
        await http.requisitar("GET", "https://loja.com.br/api")
    assert not interno.called


async def teste_destino_publico_com_https_passa(simulador, http):
    simulador.get("https://loja.com.br/api").mock(httpx.Response(200, json={"ok": True}))
    resposta = await http.requisitar("GET", "https://loja.com.br/api")
    assert ler_json(resposta) == {"ok": True}


def teste_corpo_que_nao_e_json_vira_erro_externo():
    with pytest.raises(ErroExterno):
        ler_json(httpx.Response(200, content=b"<html></html>"))


def teste_retry_after_tem_teto():
    from app.cliente_http import ESPERA_MAXIMA_RETRY_AFTER, segundos_de_espera

    assert segundos_de_espera("2") == 2.0
    assert segundos_de_espera("120") == ESPERA_MAXIMA_RETRY_AFTER
    assert segundos_de_espera("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert segundos_de_espera(None) == 0.0


async def teste_429_respeita_retry_after(simulador, http, monkeypatch):
    import app.cliente_http as modulo

    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)

    monkeypatch.setattr(modulo.asyncio, "sleep", dormir)
    respostas = iter([httpx.Response(429, headers={"retry-after": "2"}), httpx.Response(200)])
    rota = simulador.get("https://exemplo.com.br/x").mock(side_effect=lambda _: next(respostas))
    resposta = await http.requisitar("GET", "https://exemplo.com.br/x")
    assert resposta.status_code == 200
    assert rota.call_count == 2
    assert esperas and esperas[0] >= 2.0
