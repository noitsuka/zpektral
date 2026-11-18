import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.banco import Base, HistoricoPreco, criar_motor, criar_sessoes
from scripts.atualizar_precos import Estatistica, atualizar_precos, escolher, estatisticas
from testes.falsos import FonteFalsa

AGORA = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)


@pytest.fixture
async def sessoes(tmp_path):
    url = os.environ.get("URL_BANCO_TESTE") or f"sqlite+aiosqlite:///{tmp_path / 'a.db'}"
    motor = criar_motor(url)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
        await conexao.run_sync(Base.metadata.create_all)
    yield criar_sessoes(motor)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
    await motor.dispose()


def _horas(n: float) -> datetime:
    return AGORA - timedelta(hours=n)


def teste_escolhe_as_mais_procuradas_e_volateis_dentro_do_orcamento():
    candidatas = [
        Estatistica("popular", 10, 0.5, _horas(6)),
        Estatistica("rara recente", 1, 0, _horas(24)),
        Estatistica("nunca atualizada", 2, 0, None),
        Estatistica("volatil", 4, 1, _horas(7)),
        Estatistica("so agendada", 0, 1, None),
        Estatistica("popular recente", 10, 0.5, _horas(4)),
    ]
    assert escolher(candidatas, AGORA, 10) == ["popular", "volatil", "nunca atualizada"]
    assert escolher(candidatas, AGORA, 2) == ["popular", "volatil"]


def teste_validade_encurta_com_procura_e_volatilidade():
    assert Estatistica("a", 1, 0, None).validade == timedelta(hours=48)
    assert Estatistica("a", 4, 0, None).validade == timedelta(hours=12)
    assert Estatistica("a", 4, 1, None).validade == timedelta(hours=6)
    assert Estatistica("a", 100, 1, None).validade == timedelta(hours=5)
    assert Estatistica("a", 0, 0, None).validade == timedelta(hours=48)


def _linha(consulta, quando, oferta, preco, prefixo_cep="30130", agendada=False):
    return HistoricoPreco(
        observado_em=quando,
        consulta=consulta,
        oferta=oferta,
        loja="a",
        prefixo_cep=prefixo_cep,
        titulo="Air Fryer",
        preco=preco,
        status_frete="calculado",
        total=preco,
        agendada=agendada,
    )


async def teste_estatisticas_contam_buscas_de_pessoas_e_juntam_grafias(sessoes):
    linhas = [
        _linha("Air Fryer", _horas(30), "a:1", 30000),
        _linha("Air Fryer", _horas(30), "a:2", 50000),
        _linha("Air Fryer", _horas(20), "a:1", 28000),
        _linha("Air Fryer", _horas(10), "a:1", 28000),
        _linha("air fryer", _horas(5), "a:2", 50000, prefixo_cep=None),
        _linha("air fryer", _horas(2), "a:1", 27000, prefixo_cep=None, agendada=True),
        _linha("Air Fryer", AGORA - timedelta(days=8), "a:1", 1000),
        _linha("geladeira", _horas(3), "b:1", 300000, prefixo_cep=None, agendada=True),
    ]
    async with sessoes() as sessao, sessao.begin():
        sessao.add_all(linhas)
    por_consulta = {e.consulta: e for e in await estatisticas(sessoes, AGORA)}
    assert set(por_consulta) == {"Air Fryer", "geladeira"}
    air = por_consulta["Air Fryer"]
    assert air.buscas == 4
    assert air.volatilidade == 0.5
    assert air.atualizada_em == _horas(2)
    assert por_consulta["geladeira"].buscas == 0


async def _linhas(sessoes) -> list[HistoricoPreco]:
    async with sessoes() as sessao:
        return list(await sessao.scalars(select(HistoricoPreco).order_by(HistoricoPreco.id)))


async def _agendadas(sessoes) -> int:
    async with sessoes() as sessao:
        return await sessao.scalar(
            select(func.count()).select_from(HistoricoPreco).where(HistoricoPreco.agendada)
        )


TV = ("Smart TV 55 LG", 300000, "7890000000017")


async def teste_atualiza_sem_cep_e_respeita_a_validade(config, sessoes):
    agora = datetime.now(UTC)
    async with sessoes() as sessao, sessao.begin():
        sessao.add_all(
            _linha("smart tv 55", agora - timedelta(hours=h), "x:1", 100) for h in (30, 20, 10)
        )
    fonte = FonteFalsa("loja", [TV])

    feitas = await atualizar_precos(sessoes, [fonte], config, orcamento=5)
    assert feitas == ["smart tv 55"] and fonte.chamadas == 1
    novas = [r for r in await _linhas(sessoes) if r.agendada]
    assert [(r.oferta, r.prefixo_cep, r.consulta) for r in novas] == [
        ("loja:0", None, "smart tv 55")
    ]

    assert await atualizar_precos(sessoes, [fonte], config, orcamento=5) == []
    assert fonte.chamadas == 1

    outro_dia = agora + timedelta(hours=49)
    await atualizar_precos(sessoes, [fonte], config, orcamento=5, agora=outro_dia)
    assert fonte.chamadas == 2 and await _agendadas(sessoes) == 2


async def teste_mesmo_preco_ja_gravado_hoje_nao_e_regravado(config, sessoes):
    linhas = [_linha("smart tv 55", _horas(30 + h), "x:1", 100) for h in range(10)]
    linhas.append(_linha("smart tv 55", _horas(6), "loja:0", 300000, None, agendada=True))
    linhas.append(_linha("smart tv 55", _horas(30), "loja:1", 250000, None, agendada=True))
    async with sessoes() as sessao, sessao.begin():
        sessao.add_all(linhas)
    fonte = FonteFalsa("loja", [TV, ("Smart TV 55 Samsung", 250000)])

    assert await atualizar_precos(sessoes, [fonte], config, orcamento=5, agora=AGORA)
    novas = [r.oferta for r in await _linhas(sessoes) if r.agendada][2:]
    assert novas == ["loja:1"]
