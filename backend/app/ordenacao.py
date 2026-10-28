import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from app.modelos import Condicao, Oferta, Origem, Pagamento, StatusFrete

SEM_DIAS = float("inf")
DIAS_DESCONHECIDOS = 30


class Ordem(StrEnum):
    RELEVANCIA = "relevancia"
    MENOR_TOTAL = "menor_total"
    CUSTO_BENEFICIO = "custo_beneficio"
    MENOR_PRECO = "menor_preco"
    MAIOR_PRECO = "maior_preco"
    ENTREGA_RAPIDA = "entrega_rapida"
    MAIOR_DESCONTO = "maior_desconto"


class FiltroFrete(StrEnum):
    TODOS = "todos"
    GRATIS = "gratis"
    CALCULADO = "calculado"


@dataclass(frozen=True, slots=True)
class Pesos:
    preco: float = 0.5
    prazo: float = 0.2
    relevancia: float = 0.2
    confianca: float = 0.1
    decaimento: float = 0.08


@dataclass(slots=True)
class Filtros:
    ordem: Ordem = Ordem.RELEVANCIA
    pagamento: Pagamento = Pagamento.MELHOR
    relevancia_min: int = 70
    preco_min: int | None = None
    preco_max: int | None = None
    lojas: frozenset[str] = frozenset()
    origens: frozenset[Origem] = frozenset()
    voltagens: frozenset[str] = frozenset()
    voltagem_estrita: bool = False
    condicoes: frozenset[Condicao] = frozenset({Condicao.NOVO})
    frete: FiltroFrete = FiltroFrete.TODOS
    apenas_disponiveis: bool = True
    pesos: Pesos = field(default_factory=Pesos)


@dataclass(slots=True)
class FacetaLoja:
    id: str
    nome: str
    quantidade: int


@dataclass(slots=True)
class Facetas:
    lojas: list[FacetaLoja] = field(default_factory=list)
    voltagens: dict[str, int] = field(default_factory=dict)
    condicoes: dict[str, int] = field(default_factory=dict)
    preco_min: int | None = None
    preco_max: int | None = None
    com_total_exato: int = 0
    frete_gratis: int = 0
    origens: dict[str, int] = field(default_factory=dict)


def compravel(oferta: Oferta) -> bool:
    return oferta.disponivel and oferta.frete.status is not StatusFrete.NAO_ENTREGA


def certeza(oferta: Oferta) -> int:
    if oferta.total_exato:
        return 0
    if oferta.frete.status is StatusFrete.GRATIS_ANUNCIADO:
        return 1
    if oferta.frete.status is StatusFrete.ESTIMADO:
        return 2
    return 3


def confianca_da_cotacao(oferta: Oferta) -> float:
    if oferta.frete.status is StatusFrete.CALCULADO:
        return 1.0
    if oferta.frete.status is StatusFrete.GRATIS_ANUNCIADO:
        return 0.8
    if oferta.frete.status is StatusFrete.ESTIMADO:
        return 0.5
    return 0.6


def notas_custo_beneficio(
    ofertas: list[Oferta], pagamento: Pagamento, w: Pesos
) -> dict[str, float]:
    if not ofertas:
        return {}
    custos = [o.total_para(pagamento) for o in ofertas]
    baixo = min(custos)
    saida = {}
    for o, custo in zip(ofertas, custos, strict=True):
        preco = baixo / custo if custo > 0 else 1.0
        dias = o.frete.prazo_dias if o.frete.prazo_dias is not None else DIAS_DESCONHECIDOS
        entrega = math.exp(-w.decaimento * dias)
        saida[o.id] = (
            w.preco * preco
            + w.prazo * entrega
            + w.relevancia * o.relevancia / 100
            + w.confianca * confianca_da_cotacao(o)
        )
    return saida


def _chave_ordenacao(f: Filtros, conjunto: list[Oferta]) -> Callable[[Oferta], tuple]:
    pag = f.pagamento
    match f.ordem:
        case Ordem.RELEVANCIA:
            return lambda o: (-o.relevancia, o.total_para(pag), certeza(o))
        case Ordem.MENOR_TOTAL:
            return lambda o: (o.total_para(pag), certeza(o), -o.relevancia)
        case Ordem.CUSTO_BENEFICIO:
            notas = notas_custo_beneficio(conjunto, pag, f.pesos)
            return lambda o: (-notas[o.id], o.total_para(pag))
        case Ordem.MENOR_PRECO:
            return lambda o: (o.total_para(pag) - (o.frete.valor or 0), -o.relevancia)
        case Ordem.MAIOR_PRECO:
            return lambda o: (-(o.total_para(pag) - (o.frete.valor or 0)), -o.relevancia)
        case Ordem.ENTREGA_RAPIDA:
            return lambda o: (
                o.frete.prazo_dias if o.frete.prazo_dias is not None else SEM_DIAS,
                o.total_para(pag),
            )
        case Ordem.MAIOR_DESCONTO:
            return lambda o: (-o.desconto, o.total_para(pag))


def aplicar(ofertas: list[Oferta], f: Filtros) -> tuple[list[Oferta], Facetas]:
    pag = f.pagamento
    conjunto = [
        o
        for o in ofertas
        if o.relevancia >= f.relevancia_min and (not f.apenas_disponiveis or compravel(o))
    ]
    facetas = _facetas(conjunto, f)

    def manter(o: Oferta) -> bool:
        total = o.total_para(pag)
        if f.preco_min is not None and total < f.preco_min:
            return False
        if f.preco_max is not None and total > f.preco_max:
            return False
        if f.lojas and o.loja.id not in f.lojas:
            return False
        if f.origens and o.origem not in f.origens:
            return False
        if f.condicoes and o.condicao not in f.condicoes:
            return False
        if f.voltagens:
            if o.voltagem is None:
                if f.voltagem_estrita:
                    return False
            elif o.voltagem != "bivolt" and o.voltagem not in f.voltagens:
                return False
        if f.frete is FiltroFrete.CALCULADO and not o.total_exato:
            return False
        return f.frete is not FiltroFrete.GRATIS or _frete_gratis(o)

    resultado = [o for o in conjunto if manter(o)]
    resultado.sort(key=_chave_ordenacao(f, resultado))
    return resultado, facetas


def _facetas(todas: list[Oferta], f: Filtros) -> Facetas:
    condicoes = dict(Counter(str(o.condicao) for o in todas if o.condicao).most_common())
    conjunto = [o for o in todas if not f.condicoes or o.condicao in f.condicoes]
    if not conjunto:
        return Facetas(condicoes=condicoes)
    pagamento = f.pagamento
    contagens = Counter(o.loja.id for o in conjunto)
    nomes = {o.loja.id: o.loja.nome for o in conjunto}
    lojas = [FacetaLoja(i, nomes[i], n) for i, n in contagens.most_common()]
    voltagens = dict(Counter(o.voltagem for o in conjunto if o.voltagem).most_common())
    totais = [o.total_para(pagamento) for o in conjunto]
    return Facetas(
        lojas=lojas,
        voltagens=voltagens,
        condicoes=condicoes,
        preco_min=min(totais),
        preco_max=max(totais),
        com_total_exato=sum(o.total_exato for o in conjunto),
        frete_gratis=sum(_frete_gratis(o) for o in conjunto),
        origens=dict(Counter(str(o.origem) for o in conjunto).most_common()),
    )


def _frete_gratis(o: Oferta) -> bool:
    return o.frete.valor == 0 and o.frete.status in (
        StatusFrete.CALCULADO,
        StatusFrete.GRATIS_ANUNCIADO,
    )
