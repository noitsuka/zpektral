import asyncio
import logging
import re
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from app.modelos import Endereco, Frete, Oferta, OpcaoFrete, StatusFrete
from app.navegador.base import CotacaoNavegador, StatusCotacao
from app.relevancia import Consulta, pontuar_com_vendedor

log = logging.getLogger("zpektral.fontes")

_PRAZO = re.compile(r"^(\d+)\s*(bd|d|h|m)$")


@dataclass(slots=True)
class ContextoBusca:
    texto: str
    consulta: Consulta
    endereco: Endereco | None

    def relevancia_de(self, titulo: str, vendedor: str | None = None) -> int:
        return pontuar_com_vendedor(self.consulta, titulo, vendedor)

    def frete_calculando(self) -> Frete:
        return Frete(StatusFrete.CALCULANDO if self.endereco else StatusFrete.SEM_CEP)

    def frete_sem_cotacao(self) -> Frete:
        return Frete(StatusFrete.SEM_CEP if self.endereco is None else StatusFrete.NAO_INFORMADO)


Previa = Callable[[list[Oferta]], None]


class Fonte(Protocol):
    id: str
    nome: str

    @property
    def ativa(self) -> bool: ...

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]: ...


def ler_prazo(bruto: str | None) -> tuple[str | None, float | None]:
    if not bruto:
        return None, None
    achado = _PRAZO.match(bruto.strip().lower())
    if not achado:
        return bruto, None
    quantia, unidade = int(achado.group(1)), achado.group(2)
    if unidade == "bd":
        return (f"até {quantia} dia útil" if quantia == 1 else f"até {quantia} dias úteis"), quantia
    if unidade == "d":
        return (f"até {quantia} dia" if quantia == 1 else f"até {quantia} dias"), quantia
    if unidade == "h":
        return (f"até {quantia} hora" if quantia == 1 else f"até {quantia} horas"), quantia / 24
    return f"até {quantia} min", quantia / 1440


def entrega_mais_barata(opcoes: list[OpcaoFrete]) -> OpcaoFrete | None:
    entrega = [o for o in opcoes if o.tipo == "entrega"]
    if not entrega:
        return None
    return min(entrega, key=lambda o: (o.valor, o.prazo_dias if o.prazo_dias is not None else 1e9))


def montar_ofertas[T](
    id_fonte: str, entradas: Iterable[T], montar: Callable[[T, int], Oferta | None]
) -> list[Oferta]:
    ofertas = []
    for posicao, entrada in enumerate(entradas):
        try:
            oferta = montar(entrada, posicao)
        except (ValueError, TypeError, AttributeError, KeyError) as excecao:
            log.info("%s: oferta malformada ignorada (%r)", id_fonte, excecao)
            continue
        if oferta is not None:
            ofertas.append(oferta.consolidar())
    return ofertas


async def executar_no_prazo(orcamento: float, corrotinas: list[Coroutine[Any, Any, None]]) -> None:
    if not corrotinas:
        return
    if orcamento <= 0:
        for corrotina in corrotinas:
            corrotina.close()
        return
    tarefas = [asyncio.create_task(corrotina) for corrotina in corrotinas]
    try:
        await asyncio.wait(tarefas, timeout=orcamento)
    finally:
        for tarefa in tarefas:
            if not tarefa.done():
                tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
    for tarefa in tarefas:
        if not tarefa.cancelled() and (excecao := tarefa.exception()) is not None:
            log.warning("cotação falhou: %r", excecao)


def aplicar_cotacao_navegador(
    oferta: Oferta, cotacao: CotacaoNavegador | None, sem_cotacao: Frete
) -> None:
    if cotacao is not None and cotacao.status is StatusCotacao.INDISPONIVEL:
        oferta.disponivel = False
    frete = cotacao.para_frete() if cotacao is not None else None
    if frete is not None:
        oferta.frete = frete
    elif oferta.frete.status is StatusFrete.CALCULANDO:
        oferta.frete = sem_cotacao
    oferta.consolidar()


def escolher_para_cotar[T](
    itens: Iterable[T], piso: int, limite: int, oferta: Callable[[T], Oferta]
) -> list[T]:
    return sorted(
        (i for i in itens if oferta(i).relevancia >= piso),
        key=lambda i: (-oferta(i).relevancia, oferta(i).posicao),
    )[:limite]


async def cotar_pelo_navegador(
    ofertas: list[Oferta],
    alvo: list[Oferta],
    ctx: ContextoBusca,
    previa: Previa | None,
    orcamento: float,
    cotar: Callable[[dict[str, CotacaoNavegador]], Coroutine[Any, Any, None]],
    chave: Callable[[Oferta], str],
) -> list[Oferta]:
    for o in alvo:
        o.frete = ctx.frete_calculando()
    if previa is not None:
        previa([o.consolidar() for o in ofertas])
    cotacoes: dict[str, CotacaoNavegador] = {}
    await executar_no_prazo(orcamento, [cotar(cotacoes)])
    for o in alvo:
        aplicar_cotacao_navegador(o, cotacoes.get(chave(o)), ctx.frete_sem_cotacao())
    return [o.consolidar() for o in ofertas]
