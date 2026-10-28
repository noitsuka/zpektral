import os

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


@pytest.mark.parametrize(
    ("bruto", "esperadas"),
    [
        ("postgres://u:p@h/db?sslmode=require", "postgresql+asyncpg://u:p@h/db?ssl=require"),
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        (
            "postgresql://u:p@h/db?sslmode=verify-full&channel_binding=require",
            "postgresql+asyncpg://u:p@h/db?ssl=verify-full",
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

    resumo = await RegistroHistorico(sessoes).resumo_ofertas(["a:1", "b:9", "c:0"], dias=90)
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
        r = await cliente.get("/historico/ofertas", params={"ids": "carrefour:123,amazon:B0X"})
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
