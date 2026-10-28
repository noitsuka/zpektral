from collections.abc import AsyncIterator, Callable
from typing import Any

import orjson

from app.api.esquemas import InfoFonte
from app.busca import Lote, TrabalhoBusca
from app.modelos import Endereco, StatusFonte
from app.ordenacao import Filtros, aplicar


def evento(nome: str, dados: Any) -> bytes:
    return b"event: " + nome.encode() + b"\ndata: " + orjson.dumps(dados) + b"\n\n"


def _evento_lote(lote: Lote, f: Filtros) -> bytes:
    ofertas, _ = aplicar(lote.ofertas, f)
    return evento(
        "lote",
        {
            "fonte": lote.relatorio,
            "fase": lote.fase,
            "ofertas": ofertas,
            "melhor_total": ofertas[0].total_para(f.pagamento) if ofertas else None,
        },
    )


async def eventos_da_busca(
    trabalho: TrabalhoBusca, endereco: Endereco | None, fontes: list[InfoFonte], f: Filtros
) -> AsyncIterator[bytes]:
    yield evento(
        "inicio",
        {
            "consulta": trabalho.consulta,
            "endereco": endereco,
            "fontes": fontes,
            "pagamento": f.pagamento,
            "ordem": f.ordem,
        },
    )
    async for lote in trabalho.acompanhar():
        estado = lote.relatorio.status
        if estado in (StatusFonte.ERRO, StatusFonte.TEMPO_ESGOTADO):
            yield evento("falha_fonte", {"fonte": lote.relatorio})
        elif estado is StatusFonte.OK:
            yield _evento_lote(lote, f)
    resultado, facetas = aplicar(trabalho.ofertas_agrupadas(), f)
    yield evento(
        "fim",
        {
            "tempo_ms": trabalho.tempo_decorrido_ms,
            "total": len(resultado),
            "grupos_por_oferta": {o.id: o.grupo for o in resultado if o.grupo},
            "facetas": facetas,
            "fontes": trabalho.relatorios,
        },
    )


async def encerrando(
    eventos: AsyncIterator[bytes], ao_fechar: Callable[[], None]
) -> AsyncIterator[bytes]:
    try:
        async for pedaco in eventos:
            yield pedaco
    finally:
        ao_fechar()
