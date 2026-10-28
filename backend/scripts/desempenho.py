import random
import statistics
import time

import orjson

from app.agrupamento import atribuir_grupos, rebaixar_muito_abaixo
from app.modelos import Frete, Loja, Oferta, Pagamento, Parcelamento, StatusFrete
from app.ordenacao import Filtros, Ordem, aplicar
from app.relevancia import interpretar_consulta, pontuar

MARCAS = ["Samsung", "LG", "TCL", "Philco", "Semp", "Aiwa", "Philips", "Hisense"]
LOJAS = [f"loja{i}" for i in range(30)]


def ofertas(n: int, semente: int = 7) -> list[Oferta]:
    aleatorio = random.Random(semente)
    consulta = interpretar_consulta("smart tv 55")
    saida = []
    for i in range(n):
        marca = aleatorio.choice(MARCAS)
        modelo = f"{aleatorio.choice(['UN', 'QN', 'PTV'])}55{aleatorio.randint(1000, 1060)}"
        titulo = (
            f"Smart TV {marca} 55 Polegadas 4K {modelo} {aleatorio.choice(['110V', '220V', ''])}"
        )
        preco = aleatorio.randint(180_000, 600_000)
        cotada = aleatorio.random() < 0.6
        saida.append(
            Oferta(
                id=f"{i}",
                titulo=titulo,
                link="https://example.com",
                loja=Loja(aleatorio.choice(LOJAS), "Loja"),
                preco=preco,
                preco_pix=int(preco * 0.95),
                parcelamento=Parcelamento(10, preco // 10, preco, False),
                frete=Frete(
                    StatusFrete.CALCULADO if cotada else StatusFrete.NAO_INFORMADO,
                    valor=aleatorio.randint(0, 20_000) if cotada else None,
                    prazo_dias=aleatorio.randint(1, 15) if cotada else None,
                ),
                ean=f"789{aleatorio.randint(0, 300):010d}" if aleatorio.random() < 0.5 else None,
                relevancia=pontuar(consulta, titulo),
            ).consolidar()
        )
    return saida


def cronometrar(rotulo: str, funcao, rodadas: int = 200) -> None:
    amostras = []
    for _ in range(rodadas):
        inicio = time.perf_counter()
        funcao()
        amostras.append((time.perf_counter() - inicio) * 1000)
    amostras.sort()
    p50 = statistics.median(amostras)
    p95 = amostras[int(len(amostras) * 0.95) - 1]
    print(f"{rotulo:52} p50 {p50:7.2f} ms   p95 {p95:7.2f} ms")


def principal() -> None:
    for n in (500, 2000):
        conjunto = ofertas(n)
        print(f"\n{n} ofertas")
        cronometrar(
            "relevância de todos os títulos",
            lambda p=conjunto: [pontuar(interpretar_consulta("smart tv 55"), o.titulo) for o in p],
        )
        cronometrar("agrupamento (EAN + modelo)", lambda p=conjunto: atribuir_grupos(p), rodadas=50)
        atribuir_grupos(conjunto)
        for ordem in (Ordem.RELEVANCIA, Ordem.MENOR_TOTAL, Ordem.CUSTO_BENEFICIO):
            f = Filtros(ordem=ordem, pagamento=Pagamento.PIX)
            cronometrar(f"filtrar + ordenar ({ordem})", lambda f=f, p=conjunto: aplicar(p, f))
        resultado, facetas = aplicar(conjunto, Filtros())
        cronometrar(
            "rebaixar o que custa uma fração do nível", lambda p=conjunto: rebaixar_muito_abaixo(p)
        )
        pagina = {
            "ofertas": resultado[:30],
            "facetas": facetas,
        }
        cronometrar(
            "serializar página de 30 ofertas (orjson)", lambda pagina=pagina: orjson.dumps(pagina)
        )
        cronometrar("serializar todas as ofertas (orjson)", lambda r=resultado: orjson.dumps(r))


if __name__ == "__main__":
    principal()
