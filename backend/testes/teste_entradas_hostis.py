import httpx
import pytest

from app.busca import ServicoBusca
from app.cep import ServicoCep
from app.limites import Guarda
from app.main import app
from testes.falsos import FonteFalsa

PEDIDOS = [
    ("/busca", {"q": ""}),
    ("/busca", {"q": "a"}),
    ("/busca", {"q": "x" * 121}),
    ("/busca", {"q": "\x00\x01\x02"}),
    ("/busca", {"q": "tv", "cep": "abc"}),
    ("/busca", {"q": "tv", "cep": "1234567890"}),
    ("/busca", {"q": "tv", "pagina": "0"}),
    ("/busca", {"q": "tv", "pagina": "999999999999999999999"}),
    ("/busca", {"q": "tv", "por_pagina": "-1"}),
    ("/busca", {"q": "tv", "ordem": "drop table"}),
    ("/busca", {"q": "tv", "pagamento": "bitcoin"}),
    ("/busca", {"q": "tv", "condicao": "quebrado"}),
    ("/busca", {"q": "tv", "voltagem": "380v"}),
    ("/busca", {"q": "tv", "origens": "lua"}),
    ("/busca", {"q": "tv", "preco_min": "-5"}),
    ("/busca", {"q": "tv", "preco_max": "1e9"}),
    ("/busca", {"q": "tv", "relevancia_min": "101"}),
    ("/busca", {"q": "tv", "peso_preco": "nan"}),
    ("/busca", {"q": "tv", "peso_prazo": "2"}),
    ("/busca", {"q": "tv", "espera_ms": "999999"}),
    ("/busca/transmissao", {"q": "tv", "ordem": "x"}),
    ("/cep/" + "9" * 50, {}),
    ("/cep/%00%00", {}),
    ("/historico", {"grupo": "g:../../etc/passwd"}),
    ("/historico", {"grupo": "g:" + "a" * 200}),
    ("/historico", {"grupo": "g:abc", "dias": "0"}),
    ("/historico", {"grupo": "g:abc", "cep": "abc"}),
]


@pytest.fixture
async def cliente(http, config, simulador):
    simulador.route(host="testserver").pass_through()
    config.rajada_requisicoes = 10_000
    config.rajada_buscas_novas = 10_000
    app.state.ceps = ServicoCep(http, 60, 10)
    app.state.buscas = ServicoBusca([FonteFalsa("loja", [("Smart TV 55", 100000)])], config)
    app.state.guarda = Guarda.das_configuracoes(config)
    app.state.historico = None
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as c:
        yield c


@pytest.mark.parametrize(("caminho", "parametros"), PEDIDOS)
async def teste_entrada_hostil_vira_erro_do_cliente(cliente, caminho, parametros):
    r = await cliente.get(caminho, params=parametros)
    assert 400 <= r.status_code < 500 or r.status_code == 503, (r.status_code, r.text[:200])
    assert isinstance(r.json()["detail"], str)
    assert "Traceback" not in r.text


async def teste_metodos_de_escrita_nao_existem(cliente):
    for metodo in ("POST", "PUT", "DELETE", "PATCH"):
        r = await cliente.request(metodo, "/busca", params={"q": "tv"})
        assert r.status_code == 405


async def teste_origem_desconhecida_nao_recebe_cors(cliente):
    r = await cliente.options(
        "/busca",
        headers={"origin": "https://malicioso.example", "access-control-request-method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers


async def teste_marcacao_na_consulta_volta_so_como_json_inerte(cliente):
    r = await cliente.get("/busca", params={"q": "<script>alert(1)</script>"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def _casos_aleatorios(quantidade: int, semente: int = 20261027) -> list[dict[str, str]]:
    import random

    sorteio = random.Random(semente)
    pedacos = [
        "tv",
        "smart tv 55",
        "'; drop table historico; --",
        "../../etc/passwd",
        "<script>alert(1)</script>",
        "\u0000\u0007\u001b[31m",
        "🔥📺",
        "ÀÉÎÕÜ ç ñ",
        "東京",
        "%00%ff",
        " " * 40,
        "9" * 30,
        "-1",
        "1e309",
        "NaN",
        "null",
    ]
    campos = [
        "q",
        "cep",
        "pagina",
        "por_pagina",
        "ordem",
        "pagamento",
        "preco_min",
        "preco_max",
        "lojas",
        "condicao",
        "voltagem",
        "frete",
    ]
    casos = []
    for _ in range(quantidade):
        caso = {}
        for campo in sorteio.sample(campos, sorteio.randint(1, len(campos))):
            partes = sorteio.choices(pedacos, k=sorteio.randint(1, 3))
            caso[campo] = "".join(partes)[: sorteio.choice([5, 50, 200, 3000])]
        caso.setdefault("q", sorteio.choice(pedacos))
        casos.append(caso)
    return casos


@pytest.mark.parametrize("parametros", _casos_aleatorios(300))
async def teste_combinacoes_aleatorias_nunca_quebram_a_api(cliente, parametros):
    r = await cliente.get("/busca", params={**parametros, "espera_ms": "0"})
    assert r.status_code != 500, r.text[:200]
    assert r.status_code in (200, 400, 404, 422, 429, 503), (r.status_code, r.text[:200])
    corpo = r.json()
    assert "Traceback" not in r.text
    if r.status_code >= 400:
        assert isinstance(corpo["detail"], str)
