from datetime import date

import pytest

import app.navegador.base as base
from app.modelos import StatusFrete
from app.navegador.base import (
    CotacaoNavegador,
    Intervalo,
    StatusCotacao,
    ler_data_de_entrega,
    prazo_ate,
)

HOJE = date(2026, 10, 27)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Hoje", date(2026, 10, 27)),
        ("Amanhã, 28 de Outubro", date(2026, 10, 28)),
        ("quinta-feira, 30 de outubro", date(2026, 10, 30)),
        ("3 - 5 de nov.", date(2026, 11, 5)),
        ("30 out - 4 nov", date(2026, 11, 4)),
        ("05/11", date(2026, 11, 5)),
        ("05/11/2026", date(2026, 11, 5)),
        ("2 de janeiro", date(2027, 1, 2)),
        ("entrega rápida", None),
        (None, None),
    ],
)
def teste_datas_de_entrega(texto, esperada):
    assert ler_data_de_entrega(texto, HOJE) == esperada


def teste_prazo_em_dias():
    assert prazo_ate(date(2026, 10, 30), HOJE) == ("até 3 dias", 3.0, "2026-10-30")
    assert prazo_ate(date(2026, 10, 28), HOJE)[0] == "até 1 dia"
    assert prazo_ate(HOJE, HOJE)[0] == "hoje"
    assert prazo_ate(None, HOJE) == (None, None, None)


def teste_so_cotacao_completa_vira_frete():
    assert CotacaoNavegador(StatusCotacao.DESAFIO).para_frete() is None
    assert CotacaoNavegador(StatusCotacao.SEM_INFORMACAO, prazo_dias=2).para_frete() is None
    assert CotacaoNavegador(StatusCotacao.COTADO).para_frete() is None
    nao_entrega = CotacaoNavegador(StatusCotacao.NAO_ENTREGA).para_frete()
    assert nao_entrega is not None and nao_entrega.status is StatusFrete.NAO_ENTREGA


async def teste_intervalo_minimo_entre_paginas(monkeypatch):
    agora = [100.0]
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        agora[0] += segundos

    monkeypatch.setattr(base.asyncio, "sleep", dormir)
    intervalo = Intervalo(2.0, relogio=lambda: agora[0])
    await intervalo.aguardar()
    agora[0] += 0.5
    await intervalo.aguardar()
    agora[0] += 3
    await intervalo.aguardar()
    assert esperas == [pytest.approx(1.5)]
