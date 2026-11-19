import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.banco import Base, criar_motor, criar_sessoes, url_assincrona
from app.busca import ServicoBusca
from app.historico import SEGUNDOS_MESMO_PRECO, RegistroHistorico
from app.modelos import Endereco, Frete, StatusFrete
from testes.falsos import FonteFalsa

BH = Endereco("30130010", None, None, "Belo Horizonte", "MG")
RB = Endereco("69900000", None, None, "Rio Branco", "AC")


@pytest.fixture
async def sessoes(tmp_path):
    url = os.environ.get("URL_BANCO_TESTE") or f"sqlite+aiosqlite:///{tmp_path / 'h.db'}"
    motor = criar_motor(url)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
        await conexao.run_sync(Base.metadata.create_all)
    yield criar_sessoes(motor)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
    await motor.dispose()


class Relogio:
    agora = 0.0

    def __call__(self):
        return self.agora


async def executar(config, registro, endereco, fontes):
    svc = ServicoBusca(fontes, config, ao_concluir=registro.registrar)
    trabalho, _ = svc.iniciar("smart tv 55", endereco)
    await trabalho.aguardar()
    for tarefa in list(svc._em_execucao):
        await tarefa
    return trabalho


async def teste_serie_por_loja_e_regiao(config, sessoes):
    relogio = Relogio()
    registro = RegistroHistorico(sessoes, relogio=relogio)
    tv = ("Smart TV 55 LG", 300000, "7890000000017")
    await executar(config, registro, BH, [FonteFalsa("a", [tv]), FonteFalsa("b", [tv])])
    await executar(config, registro, RB, [FonteFalsa("a", [tv])])

    serie = await registro.serie("g:7890000000017", "30130010", 30)
    assert {s.loja for s in serie} == {"a", "b"}
    ponto = serie[0].pontos[0]
    assert ponto.total == 301000 and ponto.frete == 1000 and ponto.frete_exato
    assert ponto.em.tzinfo is not None

    norte = await registro.serie("g:7890000000017", "69900-000", 30)
    assert [s.loja for s in norte] == ["a"]
    todas_regioes = await registro.serie("g:7890000000017", None, 30)
    assert sum(len(s.pontos) for s in todas_regioes) == 3


async def teste_mesmo_preco_gravado_uma_vez_por_janela(config, sessoes):
    relogio = Relogio()
    registro = RegistroHistorico(sessoes, relogio=relogio)
    fonte = [FonteFalsa("a", [("Smart TV 55 LG", 300000, "7891234567895")])]
    config.segundos_cache_busca = 0
    for _ in range(3):
        await executar(config, registro, BH, fonte)
    assert len((await registro.serie("g:7891234567895", None, 30))[0].pontos) == 1

    relogio.agora += SEGUNDOS_MESMO_PRECO + 1
    await executar(config, registro, BH, fonte)
    assert len((await registro.serie("g:7891234567895", None, 30))[0].pontos) == 2


def teste_linhas_gravam_cada_oferta_e_pulam_pendentes_e_irrelevantes(config):
    from app.busca import Fase, Lote, TrabalhoBusca
    from app.modelos import Loja, Oferta, RelatorioFonte, StatusFonte

    def montar(id, ean=None, status=StatusFrete.CALCULADO, relevancia=100):
        return Oferta(
            id=id,
            titulo="Smart TV",
            link="x",
            loja=Loja("a", "A"),
            preco=100,
            ean=ean,
            frete=Frete(status, valor=0),
            relevancia=relevancia,
        ).consolidar()

    trabalho = TrabalhoBusca("tv", BH)
    relatorio = RelatorioFonte("a", "A", StatusFonte.OK)
    trabalho.adicionar(
        Lote(
            relatorio,
            [
                montar("a:1", "7891234567895"),
                montar("a:2"),
                montar("a:3", "111", StatusFrete.CALCULANDO),
                montar("a:4", relevancia=10),
            ],
            Fase.FINAL,
        )
    )
    precos, saude, _ = RegistroHistorico(None).linhas(trabalho)
    assert [(p.oferta, p.produto) for p in precos] == [("a:1", "g:7891234567895"), ("a:2", None)]
    assert precos[0].prefixo_cep == "30130"
    assert [h.loja for h in saude] == ["a"]


async def teste_erro_do_banco_nunca_chega_na_busca(config, tmp_path):
    motor = criar_motor(f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}")
    registro = RegistroHistorico(criar_sessoes(motor))
    trabalho = await executar(
        config, registro, BH, [FonteFalsa("a", [("Smart TV 55", 1, "7891234567895")])]
    )
    assert trabalho.terminou
    await motor.dispose()


ASYNCPG = "postgresql+asyncpg"


def url_postgres(esquema: str, consulta: str = "") -> str:
    usuario, senha = "usuario", "senha-ficticia"
    return f"{esquema}://{usuario}:{senha}@host/banco{consulta}"


@pytest.mark.parametrize(
    ("bruto", "esperadas"),
    [
        (url_postgres("postgres", "?sslmode=require"), url_postgres(ASYNCPG, "?ssl=require")),
        (url_postgres("postgresql"), url_postgres(ASYNCPG)),
        (
            url_postgres("postgresql", "?sslmode=verify-full&channel_binding=require"),
            url_postgres(ASYNCPG, "?ssl=verify-full"),
        ),
        ("sqlite+aiosqlite:///x.db", "sqlite+aiosqlite:///x.db"),
    ],
)
def teste_urls_de_banco_dos_provedores(bruto, esperadas):
    assert url_assincrona(bruto) == esperadas


async def teste_rota_de_historico(config, sessoes, simulador):
    from app.limites import Guarda
    from app.main import app

    simulador.route(host="testserver").pass_through()
    registro = RegistroHistorico(sessoes)
    await executar(
        config, registro, BH, [FonteFalsa("a", [("Smart TV 55 LG", 300000, "7891234567895")])]
    )
    app.state.historico = registro
    app.state.guarda = Guarda.das_configuracoes(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as cliente:
        corpo = (
            await cliente.get("/historico", params={"grupo": "g:7891234567895", "cep": "30130-010"})
        ).json()
        assert corpo[0]["loja"] == "a" and corpo[0]["menor_total"] == 301000
        app.state.historico = None
        r = await cliente.get("/historico", params={"grupo": "g:7891234567895"})
        assert r.status_code == 503


async def teste_falha_do_banco_nao_impede_gravar_na_proxima_busca(config, tmp_path, sessoes):
    motor_vazio = criar_motor(f"sqlite+aiosqlite:///{tmp_path / 'sem_tabelas.db'}")
    registro = RegistroHistorico(criar_sessoes(motor_vazio))
    tv = ("Smart TV 55 LG", 300000, "7890000000017")
    await executar(config, registro, BH, [FonteFalsa("a", [tv])])
    await motor_vazio.dispose()

    registro._sessoes = sessoes
    await executar(config, registro, BH, [FonteFalsa("a", [tv])])
    serie = await registro.serie("g:7890000000017", None, 30)
    assert [len(s.pontos) for s in serie] == [1]


async def teste_historico_antigo_e_apagado_e_o_recente_fica(config, sessoes):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.banco import HistoricoPreco, SaudeLoja

    agora = datetime.now(UTC)
    async with sessoes() as sessao, sessao.begin():
        for dias in (400, 200, 10):
            sessao.add(
                HistoricoPreco(
                    observado_em=agora - timedelta(days=dias),
                    produto="smart tv 55",
                    loja="a",
                    prefixo_cep="30130",
                    titulo="Smart TV 55",
                    preco=100,
                    status_frete="calculado",
                    total=100,
                )
            )
            sessao.add(
                SaudeLoja(
                    observado_em=agora - timedelta(days=dias),
                    loja="a",
                    status="ok",
                    tempo_decorrido_ms=1,
                    ofertas=1,
                )
            )
    registro = RegistroHistorico(sessoes, dias_retencao=180)
    apagadas = await registro.expurgar()
    assert apagadas == 4
    async with sessoes() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(HistoricoPreco)) == 1
        assert await sessao.scalar(select(func.count()).select_from(SaudeLoja)) == 1


async def teste_expurgo_roda_no_maximo_uma_vez_por_dia(config, sessoes):
    relogio = Relogio()
    registro = RegistroHistorico(sessoes, relogio=relogio, dias_retencao=180)
    chamadas = []

    async def expurgar():
        chamadas.append(relogio.agora)
        return 0

    registro.expurgar = expurgar  # type: ignore[method-assign]
    await registro.expurgar_se_preciso()
    relogio.agora += 3600
    await registro.expurgar_se_preciso()
    relogio.agora += 86400
    await registro.expurgar_se_preciso()
    assert chamadas == [0.0, 90000.0]


async def _gravar(sessoes, oferta: str, quando, preco: int, loja: str = "a") -> None:
    from app.banco import HistoricoPreco

    async with sessoes() as sessao, sessao.begin():
        sessao.add(
            HistoricoPreco(
                observado_em=quando,
                oferta=oferta,
                loja=loja,
                prefixo_cep="30130",
                titulo="Air Fryer 4L",
                preco=preco,
                status_frete="calculado",
                total=preco,
            )
        )


async def teste_resumo_por_oferta_tem_um_ponto_por_dia_com_o_menor_preco(sessoes):
    from datetime import UTC, datetime, timedelta

    agora = datetime.now(UTC).replace(hour=15, minute=0, second=0, microsecond=0)
    for dias, preco in [(40, 30000), (3, 28000), (3, 27000), (2, 29000), (0, 25000), (200, 1)]:
        await _gravar(sessoes, "a:1", agora - timedelta(days=dias), preco)
    await _gravar(sessoes, "b:9", agora - timedelta(days=1), 99900, loja="b")

    resumo = await RegistroHistorico(sessoes).resumo_ofertas(
        ["a:1", "b:9", "c:0"], dias=90, cep="30130010"
    )
    assert set(resumo) == {"a:1", "b:9"}
    pontos = resumo["a:1"]
    assert [p.preco for p in pontos] == [30000, 27000, 29000, 25000]
    assert [p.dia for p in pontos] == sorted(p.dia for p in pontos)
    assert len({p.dia for p in pontos}) == len(pontos)


async def teste_rota_de_historico_por_oferta(config, sessoes, simulador):
    from datetime import UTC, datetime, timedelta

    from app.limites import Guarda
    from app.main import app

    simulador.route(host="testserver").pass_through()
    await _gravar(sessoes, "carrefour:123", datetime.now(UTC) - timedelta(days=2), 19990)
    app.state.historico = RegistroHistorico(sessoes)
    app.state.guarda = Guarda.das_configuracoes(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as cliente:
        r = await cliente.get(
            "/historico/ofertas", params={"ids": "carrefour:123,amazon:B0X", "cep": "30130-010"}
        )
        assert r.status_code == 200
        corpo = r.json()
        assert list(corpo) == ["carrefour:123"]
        assert corpo["carrefour:123"][0]["preco"] == 19990
        assert len(corpo["carrefour:123"][0]["dia"]) == 10

        for ruim in ["", "a:1,<script>", ",".join(f"a:{i}" for i in range(51)), "a" * 200]:
            r = await cliente.get("/historico/ofertas", params={"ids": ruim})
            assert r.status_code in (400, 422), (ruim[:30], r.status_code)

        app.state.historico = None
        r = await cliente.get("/historico/ofertas", params={"ids": "carrefour:123"})
        assert r.status_code == 503


async def teste_linhas_guardam_link_imagem_preco_de_lista_e_a_busca(config, sessoes):
    from sqlalchemy import select

    from app.banco import HistoricoPreco

    fonte = FonteFalsa("a", [("Smart TV 55 LG", 300000, "7890000000017")])
    await executar(config, RegistroHistorico(sessoes), BH, [fonte])
    await executar(config, RegistroHistorico(sessoes, agendada=True), None, [fonte])
    async with sessoes() as sessao:
        linhas = (await sessao.scalars(select(HistoricoPreco).order_by(HistoricoPreco.id))).all()
    assert [(r.prefixo_cep, r.agendada) for r in linhas] == [("30130", False), (None, True)]
    assert all(r.link == "https://a.example/0" and r.consulta == "smart tv 55" for r in linhas)


async def teste_resumo_por_oferta_ignora_a_atualizacao_agendada(sessoes):
    ontem = datetime.now(UTC) - timedelta(days=1)
    await _gravar(sessoes, "a:1", ontem, 30000)
    async with sessoes() as sessao, sessao.begin():
        sessao.add(_linha("a:1", ontem, 10000, agendada=True, prefixo_cep=None))
    resumo = await RegistroHistorico(sessoes).resumo_ofertas(["a:1"], dias=90, cep="30130010")
    assert [p.preco for p in resumo["a:1"]] == [30000]


AGORA = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)


def _linha(oferta, quando, preco, **extras):
    from app.banco import HistoricoPreco

    campos = {
        "loja": oferta.split(":")[0],
        "prefixo_cep": None,
        "titulo": f"Produto {oferta}",
        "status_frete": "sem_cep",
        "link": f"https://loja.example/{oferta}",
        **extras,
    }
    return HistoricoPreco(observado_em=quando, oferta=oferta, preco=preco, total=preco, **campos)


def _serie(oferta, precos_passados, *atuais, **extras):
    linhas = [
        _linha(oferta, AGORA - timedelta(days=dias), preco)
        for dias, preco in enumerate(reversed(precos_passados), start=1)
    ]
    for horas, preco in atuais:
        linhas.append(_linha(oferta, AGORA - timedelta(hours=horas), preco, **extras))
    return linhas


async def _quedas_gravadas(sessoes):
    dez = [10000] * 6
    linhas = [
        *_serie("a:queda", dez, (1, 8500)),
        *_serie("b:limite", dez[:5], (1, 9000)),
        *_serie("a:pouca", dez[:5], (1, 9100)),
        *_serie("a:poucos_dias", dez[:3], (1, 5000)),
        *_serie("a:sem_link", dez, (1, 7000), link=None),
        *_serie("a:com_cep", dez, (1, 10000)),
        _linha("a:com_cep", AGORA - timedelta(hours=1), 6000, prefixo_cep="30130"),
        *_serie(
            "a:hoje",
            [10000, 12000, 10000, 9000, 11000],
            (3, 6000),
            (1, 8000),
            preco_original=15000,
            imagem="https://loja.example/hoje.jpg",
        ),
    ]
    linhas += [_linha("a:antiga", AGORA - timedelta(days=d), 10000) for d in range(4, 11)]
    linhas.append(_linha("a:antiga", AGORA - timedelta(days=3), 5000))
    async with sessoes() as sessao, sessao.begin():
        sessao.add_all(linhas)


async def teste_quedas_verificadas_no_historico_sem_cep(sessoes):
    await _quedas_gravadas(sessoes)
    painel = await RegistroHistorico(sessoes).quedas(30, 60, {"a": "Loja A"}, agora=AGORA)
    assert painel.janela_dias == 30 and painel.gerado_em == "2026-11-17T15:00:00+00:00"
    assert [(i.oferta, i.variacao) for i in painel.itens] == [
        ("a:hoje", -0.2),
        ("a:queda", -0.15),
        ("b:limite", -0.1),
    ]
    hoje = painel.itens[0]
    assert (hoje.preco, hoje.mediana, hoje.menor, hoje.maior) == (8000, 10000, 9000, 12000)
    assert hoje.dias_observados == 6 and hoje.visto_em == "2026-11-17T14:00:00+00:00"
    assert hoje.preco_original == 15000 and hoje.imagem == "https://loja.example/hoje.jpg"
    assert (hoje.loja.id, hoje.loja.nome, hoje.link) == (
        "a",
        "Loja A",
        "https://loja.example/a:hoje",
    )
    limite = painel.itens[2]
    assert (limite.loja.nome, limite.dias_observados, limite.imagem) == ("b", 6, None)


async def teste_quedas_respeitam_o_limite_e_ficam_em_cache(sessoes):
    await _quedas_gravadas(sessoes)
    registro = RegistroHistorico(sessoes)
    dois = await registro.quedas(30, 2, {}, agora=AGORA)
    assert [i.oferta for i in dois.itens] == ["a:hoje", "a:queda"]
    async with sessoes() as sessao, sessao.begin():
        sessao.add_all(_serie("c:nova", [10000] * 6, (1, 1000)))
    tres = await registro.quedas(30, 3, {}, agora=AGORA)
    assert tres.itens[:2] == dois.itens
    todas = await registro.quedas(30, 100, {}, agora=AGORA)
    assert all(i.oferta != "c:nova" for i in todas.itens)


async def teste_rota_de_quedas(config, sessoes, simulador):
    from app.limites import Guarda
    from app.main import app

    simulador.route(host="testserver").pass_through()
    await _quedas_gravadas(sessoes)
    registro = RegistroHistorico(sessoes)
    await registro.quedas(30, 60, {"a": "Loja A"}, agora=AGORA)
    app.state.historico = registro
    app.state.buscas = ServicoBusca([FonteFalsa("a")], config)
    app.state.guarda = Guarda.das_configuracoes(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as cliente:
        r = await cliente.get("/ofertas/quedas")
        assert r.status_code == 200
        assert "max-age" in r.headers["cache-control"]
        corpo = r.json()
        assert set(corpo) == {"janela_dias", "gerado_em", "itens"}
        assert corpo["janela_dias"] == 30
        janela = (await cliente.get("/ofertas/quedas", params={"dias": 8})).json()["janela_dias"]
        assert janela == 7
        item = corpo["itens"][0]
        assert item == {
            "oferta": "a:hoje",
            "titulo": "Produto a:hoje",
            "loja": {"id": "a", "nome": "Loja A"},
            "link": "https://loja.example/a:hoje",
            "imagem": "https://loja.example/hoje.jpg",
            "preco": 8000,
            "preco_original": 15000,
            "mediana": 10000,
            "menor": 9000,
            "maior": 12000,
            "dias_observados": 6,
            "variacao": -0.2,
            "visto_em": "2026-11-17T14:00:00+00:00",
        }

        for ruim in [{"dias": 6}, {"dias": 91}, {"limite": 0}, {"limite": 101}, {"dias": "x"}]:
            r = await cliente.get("/ofertas/quedas", params=ruim)
            assert r.status_code == 422, ruim

        app.state.historico = None
        assert (await cliente.get("/ofertas/quedas")).status_code == 503


@pytest.mark.parametrize(
    ("digitada", "gravada"),
    [
        ("Geladeira Frost Free", "geladeira frost free"),
        ("  Estante  MULTY menta ", "estante multy menta"),
        ("estante 7899307521331", "estante 7899307521331"),
        ("joao@exemplo.com geladeira", None),
        ("geladeira 123.456.789-09", None),
        ("geladeira 11987654321", None),
        ("geladeira 01310-100", None),
    ],
)
def teste_busca_gravada_e_normalizada_e_sem_dado_pessoal(digitada, gravada):
    from app.historico import consulta_gravavel

    assert consulta_gravavel(digitada) == gravada


async def teste_expurgo_apaga_o_texto_da_busca_antigo_e_mantem_o_preco(sessoes):
    from sqlalchemy import select

    from app.banco import HistoricoPreco

    async with sessoes() as sessao, sessao.begin():
        sessao.add(_linha("a:velha", datetime.now(UTC) - timedelta(days=20), 100, consulta="tv"))
        sessao.add(_linha("a:nova", datetime.now(UTC) - timedelta(days=2), 100, consulta="tv"))
    await RegistroHistorico(sessoes, dias_retencao=180).expurgar()
    async with sessoes() as sessao:
        linhas = dict(
            (await sessao.execute(select(HistoricoPreco.oferta, HistoricoPreco.consulta))).all()
        )
    assert linhas == {"a:velha": None, "a:nova": "tv"}


async def teste_resumo_por_oferta_nao_mistura_regioes(sessoes):
    ontem = datetime.now(UTC) - timedelta(days=1)
    async with sessoes() as sessao, sessao.begin():
        sessao.add(_linha("a:1", ontem, 20000, prefixo_cep="01310"))
        sessao.add(_linha("a:1", ontem, 10000, prefixo_cep="69900"))
    registro = RegistroHistorico(sessoes)
    paulista = await registro.resumo_ofertas(["a:1"], dias=90, cep="01310100")
    assert [p.preco for p in paulista["a:1"]] == [20000]
    assert await registro.resumo_ofertas(["a:1"], dias=90) == {}


async def teste_resumo_por_oferta_corta_o_passado_e_nao_os_dias_recentes(sessoes, monkeypatch):
    import app.historico as historico

    monkeypatch.setattr(historico, "LINHAS_MAXIMAS_SERIE", 3)
    agora = datetime.now(UTC)
    async with sessoes() as sessao, sessao.begin():
        for dias in range(6, 0, -1):
            sessao.add(_linha("a:1", agora - timedelta(days=dias), 10000 + dias))
    resumo = await RegistroHistorico(sessoes).resumo_ofertas(["a:1"], dias=90)
    assert [p.preco for p in resumo["a:1"]] == [10003, 10002, 10001]


async def teste_serie_por_produto_devolve_o_dia_e_nao_o_instante(sessoes):
    from datetime import time

    registro = RegistroHistorico(sessoes)
    await _gravar(sessoes, "a:1", datetime.now(UTC) - timedelta(hours=30), 30000)
    async with sessoes() as sessao, sessao.begin():
        from sqlalchemy import update

        from app.banco import HistoricoPreco

        await sessao.execute(update(HistoricoPreco).values(produto="g:x"))
    pontos = (await registro.serie("g:x", None, 30))[0].pontos
    assert all(p.em.timetz().replace(tzinfo=None) == time(0) for p in pontos)


def teste_oferta_do_mercado_livre_nao_entra_no_historico(config):
    from app.busca import Fase, Lote, TrabalhoBusca
    from app.modelos import Loja, Oferta, RelatorioFonte, StatusFonte

    trabalho = TrabalhoBusca("tv", BH)
    ofertas = [
        Oferta(f"{loja}:1", "Smart TV", "x", Loja(loja, loja), 100, relevancia=100)
        for loja in ("mercadolivre", "a")
    ]
    relatorio = RelatorioFonte("a", "A", StatusFonte.OK)
    trabalho.adicionar(Lote(relatorio, [o.consolidar() for o in ofertas], Fase.FINAL))
    precos, _, _ = RegistroHistorico(None).linhas(trabalho)
    assert [p.oferta for p in precos] == ["a:1"]


def teste_preco_da_versao_mais_barata_nao_entra_no_historico(config):
    from app.busca import Fase, Lote, TrabalhoBusca
    from app.modelos import Alerta, Loja, Oferta, RelatorioFonte, StatusFonte

    trabalho = TrabalhoBusca("fone", None)
    ofertas = [Oferta(f"s:{n}", "Fone", "x", Loja("s", "S"), 100, relevancia=100) for n in (1, 2)]
    ofertas[0].alertar(Alerta.PRECO_VARIA_POR_VERSAO)
    relatorio = RelatorioFonte("s", "S", StatusFonte.OK)
    trabalho.adicionar(Lote(relatorio, [o.consolidar() for o in ofertas], Fase.FINAL))
    precos, _, _ = RegistroHistorico(None).linhas(trabalho)
    assert [p.oferta for p in precos] == ["s:2"]
