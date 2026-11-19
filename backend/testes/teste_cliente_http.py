import asyncio
import time

import httpx
import pytest

from app.cliente_http import ErroExterno, ler_json
from app.cliente_http import _resolve_para_interno as resolver_real
from app.main import criar_app


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


@pytest.mark.parametrize(
    ("codigo", "bloqueio"), [(401, True), (403, True), (429, True), (404, False), (500, False)]
)
async def teste_erro_externo_guarda_o_status_http(simulador, http, codigo, bloqueio):
    simulador.get("https://loja.com.br/api").mock(httpx.Response(codigo))
    with pytest.raises(ErroExterno) as erro:
        await http.requisitar("GET", "https://loja.com.br/api", tentativas=0)
    assert erro.value.status == codigo
    assert erro.value.bloqueio is bloqueio


async def teste_falha_de_rede_nao_tem_status(simulador, http):
    simulador.get("https://loja.com.br/api").mock(side_effect=httpx.ConnectError("recusada"))
    with pytest.raises(ErroExterno) as erro:
        await http.requisitar("GET", "https://loja.com.br/api", tentativas=0)
    assert erro.value.status is None and erro.value.bloqueio is False


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


async def teste_cookie_de_uma_resposta_nao_vai_na_proxima(simulador, http):
    simulador.get("https://loja.com.br/a").mock(
        httpx.Response(200, json={}, headers={"set-cookie": "regiao=Ceara; Path=/"})
    )
    seguinte = simulador.get("https://loja.com.br/b").mock(httpx.Response(200, json={}))
    await http.requisitar("GET", "https://loja.com.br/a")
    await http.requisitar("GET", "https://loja.com.br/b")
    assert "cookie" not in seguinte.calls.last.request.headers


async def teste_nome_publico_que_aponta_para_rede_interna_e_recusado(simulador, http, monkeypatch):
    async def resolve(host: str) -> bool:
        return host == "localtest.me"

    monkeypatch.setattr("app.cliente_http._resolve_para_interno", resolve)
    rota = simulador.get("https://localtest.me/api").mock(httpx.Response(200, json={}))
    with pytest.raises(ErroExterno):
        await http.requisitar("GET", "https://localtest.me/api")
    assert not rota.called


async def teste_resolucao_guarda_o_resultado_por_host(monkeypatch):
    import asyncio

    from app import cliente_http

    chamadas = []

    async def getaddrinfo(host, *args, **kwargs):
        chamadas.append(host)
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(cliente_http, "_RESOLVIDOS", cliente_http.CacheComValidade(300, 8))
    assert await resolver_real("localtest.me") is True
    assert await resolver_real("localtest.me") is True
    assert chamadas == ["localtest.me"]


async def teste_resolucoes_de_nome_da_busca_nao_fazem_fila(config):
    # caso real: na Vercel, a primeira busca de uma instância nova dava ConnectTimeout em todas
    # as lojas, porque as ~200 consultas de DNS esperavam nas poucas threads do executor padrão
    app = criar_app(config.model_copy(update={"arquivo_historico_local": ""}))
    async with app.router.lifespan_context(app):
        loop = asyncio.get_running_loop()
        inicio = time.monotonic()
        await asyncio.gather(*(loop.run_in_executor(None, time.sleep, 0.5) for _ in range(64)))
        assert time.monotonic() - inicio < 1.5


def teste_conexao_tem_folga_para_a_instancia_nova():
    from app.configuracao import Configuracoes

    assert Configuracoes(_env_file=None).segundos_limite_conexao >= 6


def teste_clientes_das_lojas_dividem_o_contexto_tls(config):
    # medido: montar o contexto lê o pacote de certificados e levava 1,4 s para as ~100 lojas
    # da primeira busca de uma instância, com o servidor parado enquanto isso
    from app.cliente_http import criar_cliente

    um, outro = criar_cliente(config), criar_cliente(config)
    assert um._transport._pool._ssl_context is outro._transport._pool._ssl_context
