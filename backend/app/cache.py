import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable


class CacheComValidade[K: Hashable, V]:
    def __init__(
        self, validade: float, entradas_maximas: int, relogio: Callable[[], float] = time.monotonic
    ):
        self.validade = validade
        self.entradas_maximas = entradas_maximas
        self._relogio = relogio
        self._dados: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._carregando: dict[K, asyncio.Future[V]] = {}

    def obter(self, chave: K) -> V | None:
        entrada = self._dados.get(chave)
        if entrada is None:
            return None
        expira, valor = entrada
        if expira <= self._relogio():
            del self._dados[chave]
            return None
        self._dados.move_to_end(chave)
        return valor

    def guardar(self, chave: K, valor: V, validade: float | None = None) -> None:
        self._dados[chave] = (
            self._relogio() + (self.validade if validade is None else validade),
            valor,
        )
        self._dados.move_to_end(chave)
        while len(self._dados) > self.entradas_maximas:
            self._dados.popitem(last=False)

    async def obter_ou_carregar(self, chave: K, carregar: Callable[[], Awaitable[V]]) -> V:
        while True:
            em_cache = self.obter(chave)
            if em_cache is not None:
                return em_cache
            pendentes = self._carregando.get(chave)
            if pendentes is None:
                return await self._carregar(chave, carregar)
            try:
                return await asyncio.shield(pendentes)
            except asyncio.CancelledError:
                tarefa = asyncio.current_task()
                if not pendentes.cancelled() or (tarefa is not None and tarefa.cancelling()):
                    raise

    async def _carregar(self, chave: K, carregar: Callable[[], Awaitable[V]]) -> V:
        futuro: asyncio.Future[V] = asyncio.get_running_loop().create_future()
        self._carregando[chave] = futuro
        try:
            valor = await carregar()
        except asyncio.CancelledError:
            futuro.cancel()
            raise
        except Exception as excecao:
            futuro.set_exception(excecao)
            futuro.exception()
            raise
        else:
            self.guardar(chave, valor)
            futuro.set_result(valor)
            return valor
        finally:
            del self._carregando[chave]

    def __len__(self) -> int:
        return len(self._dados)
