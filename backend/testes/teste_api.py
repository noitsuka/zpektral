import httpx
import orjson
import pytest

from app.busca import ServicoBusca
from app.cep import ServicoCep
from app.limites import Guarda
from app.main import app
from testes.conftest import resposta_json
from testes.falsos import FonteFalsa

BH_BRASILAPI = {"cep": "30130010", "state": "MG", "city": "Belo Horizonte", "street": "Praça Sete"}


@pytest.fixture
async def cliente_api(http, config, simulador):
    simulador.get("https://brasilapi.com.br/api/cep/v2/30130010").mock(resposta_json(BH_BRASILAPI))
    simulador.get("https://viacep.com.br/ws/30130010/json/").mock(httpx.Response(503))
    simulador.get("https://brasilapi.com.br/api/cep/v2/99999999").mock(httpx.Response(404))
    simulador.get("https://viacep.com.br/ws/99999999/json/").mock(resposta_json({"erro": True}))
    simulador.route(host="testserver").pass_through()
    fontes = [
        FonteFalsa(
            "loja1",
            [
                ("Smart TV 55 LG", 300000, "7890000000017"),
                ("Smart TV 55 Samsung", 250000),
                ("Capa de chuva", 100),
            ],
        ),
        FonteFalsa("loja2", [("Smart TV 55 LG", 280000, "7890000000017")]),
        FonteFalsa("fora", erro=RuntimeError("x")),
        FonteFalsa("semchave", ativa=False),
    ]
    app.state.ceps = ServicoCep(http, 60, 10)
    app.state.buscas = ServicoBusca(fontes, config)
    app.state.guarda = Guarda.das_configuracoes(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as cliente:
        yield cliente


async def teste_busca_com_cep(cliente_api):
    r = await cliente_api.get("/busca", params={"q": "smart tv 55", "cep": "30130-010"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["endereco"]["cidade"] == "Belo Horizonte"
    assert corpo["total"] == 3
    assert [o["id"] for o in corpo["ofertas"]] == ["loja1:1", "loja2:0", "loja1:0"]
    primeira = corpo["ofertas"][0]
    assert primeira["frete"]["status"] == "calculado"
    assert primeira["total"] == 250000 + 1000 and primeira["total_exato"] is True
    estados = {f["id"]: f["status"] for f in corpo["fontes"]}
    assert estados == {"loja1": "ok", "loja2": "ok", "fora": "erro", "semchave": "desativada"}
    assert "grupos" not in corpo
    assert "server-timing" in r.headers
    assert corpo["cache"] is False

    de_novo = await cliente_api.get("/busca", params={"q": "Smart TV 55", "cep": "30130010"})
    assert de_novo.json()["cache"] is True


async def teste_filtros_e_paginacao(cliente_api):
    params = {"q": "smart tv 55", "ordem": "menor_total", "lojas": "loja1", "por_pagina": 1}
    corpo = (await cliente_api.get("/busca", params=params)).json()
    assert corpo["total"] == 2 and corpo["paginas"] == 2
    assert [o["id"] for o in corpo["ofertas"]] == ["loja1:1"]
    assert {s["id"] for s in corpo["facetas"]["lojas"]} == {"loja1", "loja2"}

    pagina2 = (await cliente_api.get("/busca", params={**params, "pagina": 2})).json()
    assert [o["id"] for o in pagina2["ofertas"]] == ["loja1:0"]

    limitado = (
        await cliente_api.get("/busca", params={"q": "smart tv 55", "preco_max": 260000})
    ).json()
    assert {o["id"] for o in limitado["ofertas"]} == {"loja1:1"}


async def teste_piso_de_relevancia_esconde_ruido(cliente_api):
    corpo = (await cliente_api.get("/busca", params={"q": "capa"})).json()
    assert [o["titulo"] for o in corpo["ofertas"]] == ["Capa de chuva"]
    baixo = (
        await cliente_api.get("/busca", params={"q": "smart tv 55", "relevancia_min": 0})
    ).json()
    assert baixo["total"] == 4


@pytest.mark.parametrize(
    ("params", "campo"),
    [
        ({}, "q"),
        ({"q": "a"}, "q"),
        ({"q": "x" * 121}, "q"),
        ({"q": "tv", "ordem": "aleatoria"}, "ordem"),
        ({"q": "tv", "relevancia_min": 101}, "relevancia_min"),
        ({"q": "tv", "por_pagina": 500}, "por_pagina"),
        ({"q": "tv", "preco_min": -1}, "preco_min"),
        ({"q": "tv", "origens": "loja,nada"}, "origens"),
        ({"q": "tv", "frete": "barato"}, "frete"),
    ],
)
async def teste_mensagens_de_validacao_em_portugues(cliente_api, params, campo):
    r = await cliente_api.get("/busca", params=params)
    assert r.status_code == 422
    assert r.json() == {"detail": f"Parâmetro inválido: {campo}"}


async def teste_cep_invalido_e_inexistente(cliente_api):
    r = await cliente_api.get("/busca", params={"q": "tv", "cep": "123"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("CEP inválido")
    r = await cliente_api.get("/busca", params={"q": "tv", "cep": "99999-999"})
    assert r.status_code == 404
    assert r.json() == {"detail": "CEP não encontrado"}


async def teste_rota_de_cep(cliente_api):
    r = await cliente_api.get("/cep/30130-010")
    assert r.status_code == 200
    assert r.json()["uf"] == "MG"
    assert "max-age" in r.headers["cache-control"]


async def teste_rota_de_fontes(cliente_api):
    corpo = (await cliente_api.get("/lojas")).json()
    assert {s["id"]: s["ativa"] for s in corpo}["semchave"] is False


async def teste_transmissao_envia_cada_fonte_e_depois_o_fim(cliente_api):
    eventos = []
    async with cliente_api.stream("GET", "/busca/transmissao", params={"q": "smart tv 55"}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        async for pedaco in r.aiter_text():
            eventos.append(pedaco)
    bruto = "".join(eventos)
    blocos = [b for b in bruto.split("\n\n") if b.strip()]
    tipos = [b.split("\n")[0].removeprefix("event: ") for b in blocos]
    assert tipos[0] == "inicio" and tipos[-1] == "fim"
    assert tipos.count("lote") == 2
    assert tipos.count("falha_fonte") == 1
    corpos_eventos = [orjson.loads(b.split("\ndata: ", 1)[1]) for b in blocos]
    loja1 = next(p for p in corpos_eventos if p.get("fonte", {}).get("id") == "loja1")
    assert [o["id"] for o in loja1["ofertas"]] == ["loja1:1", "loja1:0"]
    assert loja1["fase"] == "final"
    assert loja1["melhor_total"] == loja1["ofertas"][0]["total"]
    assert all(o["grupo"] for o in loja1["ofertas"] if o["ean"])
    concluido = corpos_eventos[-1]
    assert concluido["total"] == 3
    assert "grupos" not in concluido
    assert concluido["grupos_por_oferta"]["loja1:0"] == concluido["grupos_por_oferta"]["loja2:0"]


async def teste_saude(cliente_api):
    assert (await cliente_api.get("/saude")).json() == {"status": "ok"}


async def teste_respostas_grandes_sao_comprimidas(cliente_api):
    r = await cliente_api.get(
        "/busca",
        params={"q": "smart tv 55", "relevancia_min": 0},
        headers={"accept-encoding": "gzip"},
    )
    assert r.headers.get("content-encoding") == "gzip"


async def teste_resposta_parcial_lista_fontes_pendentes(cliente_api):
    from app.main import app as aplicacao

    lenta = FonteFalsa("lenta", [("Smart TV 55 Philco", 200000)], atraso=0.5)
    aplicacao.state.buscas.fontes.append(lenta)
    r = await cliente_api.get("/busca", params={"q": "smart tv 55 rapida", "espera_ms": 50})
    corpo = r.json()
    assert corpo["pronto"] is False
    assert "lenta" in corpo["pendentes"]
    assert {o["loja"]["id"] for o in corpo["ofertas"]} <= {"loja1", "loja2"}

    completa = (
        await cliente_api.get("/busca", params={"q": "smart tv 55 rapida", "espera_ms": 5000})
    ).json()
    assert completa["pronto"] is True and completa["pendentes"] == []
    assert completa["cache"] is True
    assert "lenta" in {o["loja"]["id"] for o in completa["ofertas"]}


async def teste_parametros_de_pagamento_voltagem_e_pesos(cliente_api):
    params = {"q": "smart tv 55", "pagamento": "pix", "ordem": "custo_beneficio"}
    assert (await cliente_api.get("/busca", params=params)).status_code == 200
    params = {"q": "smart tv 55", "voltagem": "220v,bivolt", "voltagem_estrita": "true"}
    corpo = (await cliente_api.get("/busca", params=params)).json()
    assert corpo["total"] == 0
    r = await cliente_api.get("/busca", params={"q": "tv", "voltagem": "380v"})
    assert r.json() == {"detail": "Parâmetro inválido: voltagem"}
    r = await cliente_api.get("/busca", params={"q": "tv", "peso_preco": 2})
    assert r.status_code == 422


async def teste_rota_de_fontes_inclui_saude(cliente_api):
    await cliente_api.get("/busca", params={"q": "smart tv 55"})
    corpo = {s["id"]: s for s in (await cliente_api.get("/lojas")).json()}
    assert corpo["loja1"]["saude"]["estado"] == "saudavel"
    assert corpo["fora"]["saude"]["falhas_seguidas"] == 1


async def teste_cors_expoe_os_cabecalhos_que_o_site_le(cliente_api):
    r = await cliente_api.get("/lojas", headers={"origin": "http://localhost:3000"})
    expostos = r.headers["access-control-expose-headers"].lower()
    assert "retry-after" in expostos and "x-request-id" in expostos
