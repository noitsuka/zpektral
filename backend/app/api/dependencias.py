from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError

from app.busca import CARACTERES_CONTROLE, ServicoBusca
from app.cep import ServicoCep
from app.historico import RegistroHistorico
from app.limites import Guarda
from app.modelos import Condicao, Endereco, Origem, Pagamento
from app.ordenacao import FiltroFrete, Filtros, Ordem, Pesos
from app.relevancia import interpretar_consulta

PESOS_PADRAO = Pesos()
VOLTAGENS = {"110v": "110V", "127v": "110V", "220v": "220V", "bivolt": "bivolt"}

TextoBusca = Annotated[str, Query(min_length=2, max_length=120, description="O que procurar")]
ParametroCep = Annotated[
    str | None, Query(max_length=9, description="CEP de entrega, com ou sem traço")
]


def servico_cep(requisicao: Request) -> ServicoCep:
    return requisicao.app.state.ceps


def servico_busca(requisicao: Request) -> ServicoBusca:
    return requisicao.app.state.buscas


def registro_historico(requisicao: Request) -> RegistroHistorico | None:
    return requisicao.app.state.historico


def guarda(requisicao: Request) -> Guarda:
    atual: Guarda = requisicao.app.state.guarda
    atual.registrar(requisicao)
    return atual


Ceps = Annotated[ServicoCep, Depends(servico_cep)]
Buscas = Annotated[ServicoBusca, Depends(servico_busca)]
Historico = Annotated[RegistroHistorico | None, Depends(registro_historico)]
Protegido = Annotated[Guarda, Depends(guarda)]


def texto_da_consulta(bruto: str) -> str:
    texto = " ".join(CARACTERES_CONTROLE.sub(" ", bruto).split())
    if interpretar_consulta(texto).esta_vazia:
        raise RequestValidationError([{"loc": ("query", "q")}])
    return texto


async def resolver_endereco(servico: ServicoCep, cep: str | None) -> Endereco | None:
    return await servico.resolver(cep) if cep else None


def admitir(
    requisicao: Request, atual: Guarda, servico: ServicoBusca, q: str, endereco: Endereco | None
) -> None:
    if not servico.em_cache(q, endereco):
        atual.verificar_busca_nova(requisicao, servico.em_andamento)


def _lista_csv(bruto: str | None) -> frozenset[str]:
    if not bruto:
        return frozenset()
    return frozenset(peca.strip() for peca in bruto.split(",") if peca.strip())


def _interpretar[T](bruto: str | None, converter: Callable[[str], T], campo: str) -> frozenset[T]:
    try:
        return frozenset(converter(v) for v in _lista_csv(bruto))
    except (KeyError, ValueError):
        raise RequestValidationError([{"loc": ("query", campo)}]) from None


def filtros(
    ordem: Ordem = Ordem.RELEVANCIA,
    pagamento: Annotated[
        Pagamento, Query(description="Forma de pagamento usada no total e na ordenação")
    ] = Pagamento.MELHOR,
    relevancia_min: Annotated[int, Query(ge=0, le=100)] = 70,
    condicao: Annotated[
        str, Query(description="novo, usado e/ou recondicionado, separados por vírgula")
    ] = "novo",
    preco_min: Annotated[int | None, Query(ge=0, description="Total mínimo, em centavos")] = None,
    preco_max: Annotated[int | None, Query(ge=0, description="Total máximo, em centavos")] = None,
    lojas: Annotated[str | None, Query(description="Ids de loja separados por vírgula")] = None,
    origens: Annotated[
        str | None, Query(description="loja, marketplace e/ou comparador, separados por vírgula")
    ] = None,
    voltagem: Annotated[str | None, Query(description="110V, 220V e/ou bivolt")] = None,
    voltagem_estrita: Annotated[
        bool, Query(description="Descarta também ofertas sem voltagem no título")
    ] = False,
    frete: FiltroFrete = FiltroFrete.TODOS,
    apenas_disponiveis: bool = True,
    peso_preco: Annotated[float, Query(ge=0, le=1)] = PESOS_PADRAO.preco,
    peso_prazo: Annotated[float, Query(ge=0, le=1)] = PESOS_PADRAO.prazo,
    peso_relevancia: Annotated[float, Query(ge=0, le=1)] = PESOS_PADRAO.relevancia,
    peso_confianca: Annotated[float, Query(ge=0, le=1)] = PESOS_PADRAO.confianca,
) -> Filtros:
    return Filtros(
        ordem=ordem,
        pagamento=pagamento,
        relevancia_min=relevancia_min,
        preco_min=preco_min,
        preco_max=preco_max,
        lojas=_lista_csv(lojas),
        origens=_interpretar(origens, Origem, "origens"),
        voltagens=_interpretar(voltagem, lambda v: VOLTAGENS[v.lower()], "voltagem"),
        voltagem_estrita=voltagem_estrita,
        condicoes=_interpretar(condicao, Condicao, "condicao"),
        frete=frete,
        apenas_disponiveis=apenas_disponiveis,
        pesos=Pesos(peso_preco, peso_prazo, peso_relevancia, peso_confianca),
    )


Filtrado = Annotated[Filtros, Depends(filtros)]
