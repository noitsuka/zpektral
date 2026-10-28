import asyncio
import re

import httpx
import pytest

from app.busca import ServicoBusca
from app.cep import ServicoCep
from app.limites import Guarda, LimitadorTaxa, ip_do_cliente
from app.main import app
from testes.falsos import FonteFalsa


class Relogio:
    agora = 0.0

    def __call__(self):
        return self.agora


def teste_balde_permite_rajada_e_depois_reabastece():
    relogio = Relogio()
    limitador = LimitadorTaxa(por_minuto=60, rajada=3, relogio=relogio)
    assert [limitador.consumir("a") for _ in range(3)] == [0, 0, 0]
    espera = limitador.consumir("a")
    assert 0.9 < espera <= 1.0
    assert limitador.consumir("b") == 0
    relogio.agora += 1.0
    assert limitador.consumir("a") == 0


def teste_memoria_dos_baldes_e_limitada():
    limitador = LimitadorTaxa(por_minuto=60, rajada=1, chaves_maximas=100)
    for i in range(1000):
        limitador.consumir(str(i))
    assert len(limitador._baldes) == 100


class RequisicaoFalsa:
    def __init__(self, host, encaminhado=None):
        self.client = type("C", (), {"host": host})
        self.headers = {"x-forwarded-for": encaminhado} if encaminhado else {}


def teste_cabecalho_encaminhado_so_vale_atras_de_proxy():
    req = RequisicaoFalsa("10.0.0.1", "203.0.113.9")
    assert ip_do_cliente(req, confiar_proxy=False) == "10.0.0.1"
    assert ip_do_cliente(req, confiar_proxy=True) == "203.0.113.9"
    assert ip_do_cliente(RequisicaoFalsa("10.0.0.1"), confiar_proxy=True) == "10.0.0.1"


def teste_valor_forjado_pelo_cliente_no_encaminhado_e_ignorado():
    forjado = RequisicaoFalsa("10.0.0.1", "1.2.3.4, 198.51.100.7")
    assert ip_do_cliente(forjado, confiar_proxy=True) == "198.51.100.7"


def teste_ipv6_e_agrupado_por_prefixo_64():
    a = RequisicaoFalsa("2001:db8:aa:bb:1::1")
    b = RequisicaoFalsa("2001:db8:aa:bb:ffff::2")
    c = RequisicaoFalsa("2001:db8:aa:bc::1")
    assert ip_do_cliente(a, False) == ip_do_cliente(b, False) != ip_do_cliente(c, False)
    assert ip_do_cliente(RequisicaoFalsa("::ffff:203.0.113.9"), False) == "203.0.113.9"


@pytest.fixture
async def cliente(http, config, simulador):
    simulador.route(host="testserver").pass_through()
    config.rajada_buscas_novas = 2
    config.buscas_novas_por_minuto = 1
    config.rajada_requisicoes = 1000
    config.transmissoes_por_ip = 1
    config.maximo_buscas_em_andamento = 50
    app.state.ceps = ServicoCep(http, 60, 10)
    app.state.buscas = ServicoBusca(
        [FonteFalsa("loja", [("Smart TV 55 LG", 100000)], atraso=0.05)], config
    )
    app.state.guarda = Guarda.das_configuracoes(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as c:
        yield c


async def teste_buscas_novas_sao_limitadas_e_as_em_cache_nao(cliente):
    for q in ("tv 1", "tv 2"):
        assert (await cliente.get("/busca", params={"q": q})).status_code == 200
    r = await cliente.get("/busca", params={"q": "tv 3"})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert r.json()["detail"].startswith("Muitas buscas novas")
    for _ in range(10):
        assert (await cliente.get("/busca", params={"q": "TV 1"})).status_code == 200


async def teste_buscas_demais_em_andamento_dao_503(cliente, config):
    app.state.guarda = Guarda.das_configuracoes(config)
    app.state.guarda.maximo_em_andamento = 0
    r = await cliente.get("/busca", params={"q": "tv"})
    assert r.status_code == 503 and "retry-after" in r.headers


async def teste_limite_geral_de_requisicoes(cliente, config):
    config.rajada_requisicoes = 3
    config.requisicoes_por_minuto = 1
    app.state.guarda = Guarda.das_configuracoes(config)
    codigos = [(await cliente.get("/lojas")).status_code for _ in range(5)]
    assert codigos == [200, 200, 200, 429, 429]


async def teste_uma_transmissao_aberta_por_endereco(cliente):
    app.state.guarda.abrir_transmissao("127.0.0.1")
    ocupado = await cliente.get("/busca/transmissao", params={"q": "tv lenta"})
    assert ocupado.status_code == 429
    app.state.guarda.fechar_transmissao("127.0.0.1")
    aceitos = await cliente.get("/busca/transmissao", params={"q": "tv lenta"})
    assert aceitos.status_code == 200
    assert app.state.guarda.transmissoes == {}


async def teste_cabecalhos_de_seguranca(cliente):
    r = await cliente.get("/lojas")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    documentacao = await cliente.get("/docs")
    assert "content-security-policy" not in documentacao.headers


@pytest.mark.parametrize("q", ["!!!", "de para", "\x00\x01", "  -- "])
async def teste_consultas_sem_produto_sao_recusadas(cliente, q):
    r = await cliente.get("/busca", params={"q": q})
    assert r.status_code == 422


async def teste_caracteres_de_controle_saem_da_consulta(cliente):
    r = await cliente.get("/busca", params={"q": "smart\x00tv‮ 55"})
    assert r.status_code == 200
    assert r.json()["consulta"] == "smart tv 55"


@pytest.mark.parametrize("grupo", ["x", "g:", "g:<script>", "g:" + "a" * 100, "G:ABC"])
async def teste_grupo_do_historico_e_validado(cliente, grupo):
    app.state.historico = None
    r = await cliente.get("/historico", params={"grupo": grupo})
    assert r.status_code == 422


async def teste_erros_inesperados_nao_vazam(cliente, config):
    class Quebrado:
        saude = None

        def __init__(self):
            self.fontes = []

        def em_cache(self, *_):
            raise RuntimeError("segredo interno")

    app.state.buscas = Quebrado()
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as c:
        r = await c.get("/busca", params={"q": "tv"}, headers={"origin": config.origens_cors[0]})
    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] == config.origens_cors[0]
    assert r.headers["x-content-type-options"] == "nosniff"
    corpo = r.json()
    assert corpo["detail"] == "Erro interno"
    assert re.fullmatch(r"[0-9a-f]{32}", corpo["id"])
    assert r.headers["x-request-id"] == corpo["id"]
    assert "segredo" not in r.text


async def teste_toda_resposta_leva_id_de_requisicao(cliente):
    r = await cliente.get("/lojas")
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"])


@pytest.mark.parametrize(
    ("enviado", "mantido"),
    [("abc12345-trace", True), ("x" * 65, False), ("<script>", False), ("", False)],
)
async def teste_id_de_requisicao_valido_recebido_e_mantido(cliente, enviado, mantido):
    r = await cliente.get("/lojas", headers={"x-request-id": enviado})
    assert (r.headers["x-request-id"] == enviado) is mantido


async def teste_vaga_de_transmissao_liberada_quando_o_cliente_sai(cliente):
    async with cliente.stream("GET", "/busca/transmissao", params={"q": "tv desiste"}) as r:
        async for _ in r.aiter_bytes():
            break
    await asyncio.sleep(0.1)
    assert app.state.guarda.transmissoes == {}


async def teste_vaga_liberada_quando_a_busca_falha_antes_da_transmissao(cliente, monkeypatch):
    def quebrar(*_):
        raise RuntimeError("falha interna")

    monkeypatch.setattr(app.state.buscas, "iniciar", quebrar)
    r = await cliente.get("/busca/transmissao", params={"q": "tv"})
    assert r.status_code == 500
    assert app.state.guarda.transmissoes == {}


def teste_vaga_liberada_uma_vez_mesmo_chamada_varias_vezes():
    guarda = Guarda(
        por_minuto=60,
        rajada=10,
        novas_por_minuto=60,
        rajada_novas=10,
        maximo_em_andamento=10,
        transmissoes_por_ip=2,
        confiar_proxy=False,
    )
    a = guarda.abrir_transmissao("1.1.1.1")
    b = guarda.abrir_transmissao("1.1.1.1")
    a.liberar()
    a.liberar()
    assert guarda.transmissoes == {"1.1.1.1": 1}
    b.liberar()
    assert guarda.transmissoes == {}


def teste_transmissao_que_nunca_comecou_libera_a_vaga():
    import gc
    import weakref

    from app.api.eventos import encerrando

    guarda = Guarda(
        por_minuto=60,
        rajada=10,
        novas_por_minuto=60,
        rajada_novas=10,
        maximo_em_andamento=10,
        transmissoes_por_ip=1,
        confiar_proxy=False,
    )
    vaga = guarda.abrir_transmissao("1.1.1.1")

    async def eventos():
        yield b""

    corpo = encerrando(eventos(), vaga.liberar)
    weakref.finalize(corpo, vaga.liberar)
    del corpo
    gc.collect()
    assert guarda.transmissoes == {}
