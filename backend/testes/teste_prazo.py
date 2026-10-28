import asyncio
import logging

import pytest

from app.fontes.base import executar_no_prazo


async def teste_cancelar_o_chamador_cancela_as_cotacoes():
    terminadas = []

    async def cotacao():
        await asyncio.sleep(5)
        terminadas.append(1)

    antes = len(asyncio.all_tasks())
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await executar_no_prazo(10, [cotacao() for _ in range(5)])
    await asyncio.sleep(0)
    assert len(asyncio.all_tasks()) == antes
    assert terminadas == []


async def teste_prazo_estourado_cancela_as_pendentes():
    async def lenta():
        await asyncio.sleep(5)

    antes = len(asyncio.all_tasks())
    await executar_no_prazo(0.02, [lenta(), lenta()])
    assert len(asyncio.all_tasks()) == antes


async def teste_erro_inesperado_numa_cotacao_e_registrado(caplog):
    async def quebra():
        raise KeyError("campo")

    async def ok():
        return None

    with caplog.at_level(logging.WARNING, logger="zpektral.fontes"):
        await executar_no_prazo(1, [quebra(), ok()])
    assert "KeyError" in caplog.text
