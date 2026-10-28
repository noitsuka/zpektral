import asyncio

import pytest

from app.cache import CacheComValidade


class Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora


def teste_expiracao_e_validade_personalizada():
    relogio = Relogio()
    cache = CacheComValidade(10, 100, relogio=relogio)
    cache.guardar("a", 1)
    cache.guardar("b", 2, validade=1)
    relogio.agora = 5
    assert cache.obter("a") == 1
    assert cache.obter("b") is None
    relogio.agora = 10
    assert cache.obter("a") is None


def teste_descarte_mantem_os_usados_recentemente():
    cache = CacheComValidade(100, 2)
    cache.guardar("a", 1)
    cache.guardar("b", 2)
    cache.obter("a")
    cache.guardar("c", 3)
    assert cache.obter("a") == 1
    assert cache.obter("b") is None
    assert len(cache) == 2


async def teste_faltas_simultaneas_dividem_uma_carga():
    cache = CacheComValidade(100, 10)
    chamadas = 0

    async def carregar():
        nonlocal chamadas
        chamadas += 1
        await asyncio.sleep(0.05)
        return "value"

    resultados = await asyncio.gather(*(cache.obter_ou_carregar("k", carregar) for _ in range(50)))
    assert resultados == ["value"] * 50
    assert chamadas == 1


async def teste_falhas_sao_divididas_mas_nao_guardadas():
    cache = CacheComValidade(100, 10)
    chamadas = 0

    async def carregar():
        nonlocal chamadas
        chamadas += 1
        await asyncio.sleep(0.01)
        raise LookupError("boom")

    resultados = await asyncio.gather(
        *(cache.obter_ou_carregar("k", carregar) for _ in range(5)), return_exceptions=True
    )
    assert all(isinstance(r, LookupError) for r in resultados)
    assert chamadas == 1
    with pytest.raises(LookupError):
        await cache.obter_ou_carregar("k", carregar)
    assert chamadas == 2


async def teste_lider_cancelado_nao_contamina_a_chave():
    cache = CacheComValidade(100, 10)

    async def lenta():
        await asyncio.sleep(10)
        return 1

    lider = asyncio.create_task(cache.obter_ou_carregar("k", lenta))
    await asyncio.sleep(0)
    lider.cancel()
    with pytest.raises(asyncio.CancelledError):
        await lider

    async def rapida():
        return 2

    assert await cache.obter_ou_carregar("k", rapida) == 2


async def teste_seguidor_carrega_de_novo_quando_o_lider_e_cancelado():
    cache = CacheComValidade(100, 10)
    chamadas = 0

    async def carregar():
        nonlocal chamadas
        chamadas += 1
        await asyncio.sleep(0.05)
        return chamadas

    lider = asyncio.create_task(cache.obter_ou_carregar("k", carregar))
    await asyncio.sleep(0)
    seguidor = asyncio.create_task(cache.obter_ou_carregar("k", carregar))
    await asyncio.sleep(0)
    lider.cancel()

    assert await seguidor == 2
    assert lider.cancelled()


async def teste_seguidor_cancelado_continua_cancelado():
    cache = CacheComValidade(100, 10)

    async def lenta():
        await asyncio.sleep(10)
        return 1

    lider = asyncio.create_task(cache.obter_ou_carregar("k", lenta))
    await asyncio.sleep(0)
    seguidor = asyncio.create_task(cache.obter_ou_carregar("k", lenta))
    await asyncio.sleep(0)
    seguidor.cancel()
    with pytest.raises(asyncio.CancelledError):
        await seguidor
    lider.cancel()
    with pytest.raises(asyncio.CancelledError):
        await lider
