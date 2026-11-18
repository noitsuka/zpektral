import argparse
import asyncio
import random
import statistics
import time
import tracemalloc

from app.busca import ServicoBusca
from app.cliente_http import ErroExterno
from app.configuracao import Configuracoes
from app.fontes.base import ContextoBusca, Previa
from app.modelos import Loja, Oferta, StatusFonte

MARCAS = ["Brastemp", "Consul", "Electrolux", "Samsung", "LG", "Philco", "Midea", "Panasonic"]


class LojaSimulada:
    def __init__(self, indice: int, sorteio: random.Random):
        self.id = self.nome = f"loja{indice}"
        self._sorteio = sorteio

    @property
    def ativa(self) -> bool:
        return True

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        sorte = self._sorteio.random()
        await asyncio.sleep(self._sorteio.lognormvariate(0, 0.6))
        if sorte < 0.05:
            await asyncio.sleep(60)
        if sorte < 0.10:
            raise ErroExterno("recusou", 403)
        if sorte < 0.20:
            raise ErroExterno("falhou", 500)
        ofertas = []
        for i in range(30):
            titulo = f"{ctx.texto} {self._sorteio.choice(MARCAS)} {i} 110V Inox"
            ofertas.append(
                Oferta(
                    id=f"{self.id}:{i}:1",
                    titulo=titulo,
                    link=f"https://{self.id}.com.br/p/{i}",
                    loja=Loja(self.id, self.nome),
                    preco=self._sorteio.randint(50_000, 500_000),
                    relevancia=ctx.relevancia_de(titulo),
                ).consolidar()
            )
        if previa is not None:
            previa(ofertas)
        await asyncio.sleep(self._sorteio.uniform(0.2, 2))
        return ofertas


async def medir(lojas: int, simultaneas: int, rodadas: int) -> None:
    config = Configuracoes(_env_file=None)
    sorteio = random.Random(7)
    servico = ServicoBusca([LojaSimulada(i, sorteio) for i in range(lojas)], config)
    tracemalloc.start()
    tempos: list[float] = []
    estados: dict[str, int] = {}
    cpu = time.process_time()
    inicio_total = time.perf_counter()

    async def uma(consulta: str) -> None:
        inicio = time.perf_counter()
        trabalho, _ = servico.iniciar(consulta, None)
        await trabalho.aguardar()
        trabalho.ofertas_agrupadas()
        tempos.append(time.perf_counter() - inicio)
        for r in trabalho.relatorios:
            estados[r.status.value] = estados.get(r.status.value, 0) + 1

    for rodada in range(rodadas):
        await asyncio.gather(*(uma(f"geladeira {rodada} {i}") for i in range(simultaneas)))
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    ordenados = sorted(tempos)
    p95 = ordenados[int(0.95 * (len(ordenados) - 1))]
    print(
        f"{lojas} lojas, {simultaneas} buscas simultâneas x {rodadas}: "
        f"p50 {statistics.median(tempos):.1f} s, p95 {p95:.1f} s, "
        f"CPU {time.process_time() - cpu:.1f} s em {time.perf_counter() - inicio_total:.1f} s, "
        f"pico {pico / 1e6:.0f} MB, cache com {len(servico._trabalhos)} buscas, "
        f"fontes {estados} (bloqueada={StatusFonte.BLOQUEADA.value in estados})"
    )


async def medir_chegadas(
    lojas: int, taxa: float, segundos: float, limite: int, repetidas: float
) -> None:
    """Buscas chegando a `taxa` por segundo, com a mesma admissão da API."""
    config = Configuracoes(_env_file=None)
    sorteio = random.Random(11)
    servico = ServicoBusca([LojaSimulada(i, sorteio) for i in range(lojas)], config)
    tracemalloc.start()
    contagem = {"novas": 0, "do_cache": 0, "recusadas": 0}
    tempos: list[float] = []
    simultaneas: list[int] = []
    tarefas = []
    cpu, inicio = time.process_time(), time.perf_counter()

    async def uma(consulta: str) -> None:
        comeco = time.perf_counter()
        trabalho, _ = servico.iniciar(consulta, None)
        await trabalho.aguardar()
        tempos.append(time.perf_counter() - comeco)

    n = 0
    while time.perf_counter() - inicio < segundos:
        n += 1
        # parte das buscas repete as mais procuradas: é onde deduplicação e cache ajudam
        if sorteio.random() < repetidas:
            consulta = f"geladeira popular {sorteio.randint(1, 5)}"
        else:
            consulta = f"geladeira {n}"
        if servico.em_cache(consulta, None):
            contagem["do_cache"] += 1
            tarefas.append(asyncio.create_task(uma(consulta)))
        elif servico.em_andamento >= limite:
            contagem["recusadas"] += 1
        else:
            contagem["novas"] += 1
            tarefas.append(asyncio.create_task(uma(consulta)))
        simultaneas.append(servico.em_andamento)
        await asyncio.sleep(sorteio.expovariate(taxa))
    await asyncio.gather(*tarefas)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    decorrido = time.perf_counter() - inicio
    total = sum(contagem.values())
    ordenados = sorted(tempos)
    print(
        f"taxa {taxa}/s, limite {limite}, {repetidas:.0%} repetidas: {total} chegadas, "
        f"{contagem['novas']} novas, {contagem['do_cache']} do cache, "
        f"{contagem['recusadas']} recusadas ({contagem['recusadas'] / total:.0%}); "
        f"atendidas p50 {statistics.median(tempos):.1f} s, "
        f"p95 {ordenados[int(0.95 * (len(ordenados) - 1))]:.1f} s; "
        f"simultâneas máx {max(simultaneas)}; CPU {(time.process_time() - cpu) / decorrido:.0%}; "
        f"pico {pico / 1e6:.0f} MB"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mede CPU, memória e latência da busca com lojas falsas, sem tocar as reais."
    )
    parser.add_argument("--lojas", type=int, default=98)
    parser.add_argument("--simultaneas", type=int, default=8)
    parser.add_argument("--rodadas", type=int, default=3)
    parser.add_argument("--taxa", type=float, help="buscas por segundo (modo chegadas)")
    parser.add_argument("--segundos", type=float, default=60)
    parser.add_argument("--limite", type=int, default=8, help="buscas novas ao mesmo tempo")
    parser.add_argument("--repetidas", type=float, default=0.3, help="fração de buscas repetidas")
    args = parser.parse_args()
    if args.taxa:
        asyncio.run(
            medir_chegadas(args.lojas, args.taxa, args.segundos, args.limite, args.repetidas)
        )
    else:
        asyncio.run(medir(args.lojas, args.simultaneas, args.rodadas))


if __name__ == "__main__":
    main()
