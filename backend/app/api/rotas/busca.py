import time
import weakref
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.api.dependencias import (
    Buscas,
    Ceps,
    Filtrado,
    ParametroCep,
    Protegido,
    TextoBusca,
    admitir,
    resolver_endereco,
    texto_da_consulta,
)
from app.api.esquemas import PaginaBusca, info_das_fontes
from app.api.eventos import encerrando, eventos_da_busca
from app.api.respostas import RespostaJson
from app.ordenacao import aplicar

roteador = APIRouter()


@roteador.get("/busca", response_model=PaginaBusca, summary="Busca, filtra e ordena ofertas")
async def buscar(
    requisicao: Request,
    guarda: Protegido,
    q: TextoBusca,
    f: Filtrado,
    servico: Buscas,
    ceps: Ceps,
    cep: ParametroCep = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 30,
    espera_ms: Annotated[
        int,
        Query(
            ge=0,
            le=30_000,
            description="Quanto esperar pelas lojas. As que responderem depois ficam em "
            "`pendentes` e chegam por /busca/transmissao, ou numa nova chamada, já do cache.",
        ),
    ] = 1500,
) -> Response:
    inicio = time.perf_counter()
    q = texto_da_consulta(q)
    endereco = await resolver_endereco(ceps, cep)
    admitir(requisicao, guarda, servico, q, endereco)
    trabalho, em_cache = servico.iniciar(q, endereco)
    await trabalho.aguardar(espera_ms / 1000)

    filtradas, facetas = aplicar(trabalho.ofertas_agrupadas(), f)
    primeira = (pagina - 1) * por_pagina
    resultado = PaginaBusca(
        consulta=q,
        endereco=endereco,
        pronto=trabalho.terminou,
        pendentes=trabalho.pendentes,
        total=len(filtradas),
        pagina=pagina,
        por_pagina=por_pagina,
        paginas=-(-len(filtradas) // por_pagina),
        ofertas=filtradas[primeira : primeira + por_pagina],
        facetas=facetas,
        fontes=trabalho.relatorios,
        tempo_ms=trabalho.tempo_decorrido_ms,
        cache=em_cache,
    )
    levou = (time.perf_counter() - inicio) * 1000
    return RespostaJson(resultado, headers={"server-timing": f"app;dur={levou:.1f}"})


@roteador.get(
    "/busca/transmissao",
    summary="Ofertas de cada loja assim que ela responde (Server-Sent Events)",
    description="Eventos: `inicio` (uma vez), `lote` (por lote de cada loja: primeiro o "
    "catálogo, depois o lote final com o frete do CEP, que substitui o anterior), "
    "`falha_fonte` (loja que falhou ou estourou o tempo) e `fim` (agrupamento final). "
    "As ofertas de cada lote já chegam filtradas e ordenadas pelos parâmetros de /busca.",
    response_class=StreamingResponse,
)
async def buscar_transmissao(
    requisicao: Request,
    guarda: Protegido,
    q: TextoBusca,
    f: Filtrado,
    servico: Buscas,
    ceps: Ceps,
    cep: ParametroCep = None,
) -> StreamingResponse:
    q = texto_da_consulta(q)
    endereco = await resolver_endereco(ceps, cep)
    admitir(requisicao, guarda, servico, q, endereco)
    vaga = guarda.abrir_transmissao(guarda.ip(requisicao))
    try:
        trabalho, _ = servico.iniciar(q, endereco)
        eventos = eventos_da_busca(trabalho, endereco, info_das_fontes(servico), f)
        corpo = encerrando(eventos, vaga.liberar)
        weakref.finalize(corpo, vaga.liberar)
    except BaseException:
        vaga.liberar()
        raise
    return StreamingResponse(
        corpo,
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )
