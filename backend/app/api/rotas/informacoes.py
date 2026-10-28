import re
from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import Response

from app.api.dependencias import Buscas, Ceps, Historico, ParametroCep, Protegido
from app.api.esquemas import InfoFonte, info_das_fontes
from app.api.respostas import RespostaJson
from app.cep import normalizar_cep
from app.cliente_http import ErroExterno
from app.historico import OFERTAS_POR_CONSULTA, TAMANHO_MAXIMO_OFERTA, PontoDia, SerieLoja
from app.modelos import Endereco

roteador = APIRouter()
_ID_OFERTA = re.compile(rf"^[A-Za-z0-9][A-Za-z0-9:._/-]{{0,{TAMANHO_MAXIMO_OFERTA - 1}}}$")


@roteador.get("/saude", include_in_schema=False)
async def saude() -> dict[str, str]:
    return {"status": "ok"}


@roteador.get("/cep/{cep}", response_model=Endereco, summary="Endereço de um CEP")
async def obter_cep(
    cep: Annotated[str, Path(max_length=9)], guarda: Protegido, ceps: Ceps
) -> Response:
    try:
        endereco = await ceps.consultar(cep)
    except ErroExterno:
        return RespostaJson(
            {"detail": "Consulta de CEP indisponível no momento"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RespostaJson(endereco, headers={"cache-control": "public, max-age=86400"})


@roteador.get("/lojas", response_model=list[InfoFonte], summary="Fontes consultadas e sua saúde")
async def obter_fontes(guarda: Protegido, servico: Buscas) -> Response:
    return RespostaJson(info_das_fontes(servico))


@roteador.get(
    "/historico",
    response_model=list[SerieLoja],
    summary="Histórico de preço e frete de um produto, por loja e região de CEP",
)
async def obter_historico(
    guarda: Protegido,
    historico: Historico,
    grupo: Annotated[str, Query(pattern=r"^g:[a-z0-9/]{1,78}$", description="`grupo` da oferta")],
    cep: ParametroCep = None,
    dias: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Response:
    if historico is None:
        return RespostaJson(
            {"detail": "Histórico de preços desativado neste servidor"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    regiao = normalizar_cep(cep) if cep else None
    return RespostaJson(await historico.serie(grupo, regiao, dias))


@roteador.get(
    "/historico/ofertas",
    response_model=dict[str, list[PontoDia]],
    summary="Menor preço de cada dia de cada oferta, na própria loja",
)
async def obter_historico_ofertas(
    guarda: Protegido,
    historico: Historico,
    ids: Annotated[
        str,
        Query(max_length=8200, description="ids das ofertas separados por vírgula, até 50"),
    ],
    dias: Annotated[int, Query(ge=7, le=365)] = 90,
) -> Response:
    lista = list(dict.fromkeys(i for i in ids.split(",") if i))
    if not lista or len(lista) > OFERTAS_POR_CONSULTA or not all(map(_ID_OFERTA.match, lista)):
        return RespostaJson(
            {"detail": f"Informe de 1 a {OFERTAS_POR_CONSULTA} ids de oferta válidos"},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if historico is None:
        return RespostaJson(
            {"detail": "Histórico de preços desativado neste servidor"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RespostaJson(await historico.resumo_ofertas(lista, dias))
