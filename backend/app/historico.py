import logging
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from itertools import groupby

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.banco import HistoricoPreco, SaudeLoja
from app.busca import TrabalhoBusca
from app.cache import CacheComValidade
from app.modelos import Loja, Oferta, StatusFonte, StatusFrete, instante_iso

log = logging.getLogger("zpektral.historico")

SEGUNDOS_MESMO_PRECO = 3600
TAMANHO_MAXIMO_PRODUTO = 80
CHAVES_LEMBRADAS = 200_000
LINHAS_MAXIMAS_SERIE = 5_000
INTERVALO_EXPURGO_S = 86_400
RELEVANCIA_MINIMA_HISTORICO = 70
TAMANHO_MAXIMO_OFERTA = 160
OFERTAS_POR_CONSULTA = 50
HORARIO_DE_BRASILIA = timezone(timedelta(hours=-3))
TAMANHO_MAXIMO_CONSULTA = 120
SEGUNDOS_CACHE_QUEDAS = 300
DIAS_MINIMOS_QUEDA = 5
HORAS_VISTA_RECENTE = 48


@dataclass(slots=True)
class Ponto:
    em: datetime
    preco: int
    preco_pix: int | None
    frete: int | None
    total: int
    frete_exato: bool


@dataclass(slots=True)
class PontoDia:
    dia: date
    preco: int


@dataclass(slots=True)
class SerieLoja:
    loja: str
    vendedor: str | None
    menor_total: int
    atual: int
    pontos: list[Ponto]


@dataclass(slots=True)
class QuedaPreco:
    oferta: str
    titulo: str
    loja: Loja
    link: str
    imagem: str | None
    preco: int
    preco_original: int | None
    mediana: int
    menor: int
    maior: int
    dias_observados: int
    variacao: float
    visto_em: str


@dataclass(slots=True)
class PainelQuedas:
    janela_dias: int
    gerado_em: str
    itens: list[QuedaPreco]


class RegistroHistorico:
    def __init__(
        self,
        sessoes: async_sessionmaker,
        relogio=time.monotonic,
        dias_retencao: int = 180,
        agendada: bool = False,
    ):
        self._sessoes = sessoes
        self._relogio = relogio
        self._dias_retencao = dias_retencao
        self._agendada = agendada
        self._ultimo_expurgo: float | None = None
        self._gravados: CacheComValidade[tuple, int] = CacheComValidade(
            SEGUNDOS_MESMO_PRECO, CHAVES_LEMBRADAS, relogio
        )
        self._quedas: CacheComValidade[tuple[int, int], PainelQuedas] = CacheComValidade(
            SEGUNDOS_CACHE_QUEDAS, 32, relogio
        )

    def linhas(
        self, trabalho: TrabalhoBusca
    ) -> tuple[list[HistoricoPreco], list[SaudeLoja], dict[tuple, int]]:
        prefixo_cep = trabalho.endereco.cep[:5] if trabalho.endereco else None
        precos = []
        chaves: dict[tuple, int] = {}
        for o in trabalho.ofertas_agrupadas():
            if not _gravavel(o):
                continue
            chave = (o.id, prefixo_cep)
            if chave in chaves or self._gravados.obter(chave) == o.total:
                continue
            chaves[chave] = o.total
            precos.append(
                HistoricoPreco(
                    produto=o.grupo if o.grupo and len(o.grupo) <= TAMANHO_MAXIMO_PRODUTO else None,
                    oferta=o.id,
                    ean=o.ean,
                    loja=o.loja.id,
                    vendedor=(o.vendedor or "")[:120] or None,
                    prefixo_cep=prefixo_cep,
                    titulo=o.titulo[:300],
                    preco=o.preco,
                    preco_pix=o.preco_pix,
                    frete=o.frete.valor,
                    status_frete=o.frete.status,
                    total=o.total,
                    preco_original=o.preco_original,
                    link=o.link or None,
                    imagem=o.imagem,
                    consulta=trabalho.consulta[:TAMANHO_MAXIMO_CONSULTA],
                    agendada=self._agendada,
                )
            )
        saude = [
            SaudeLoja(
                loja=r.id,
                status=r.status,
                tempo_decorrido_ms=r.tempo_ms,
                ofertas=r.ofertas,
                mensagem=(r.mensagem or "")[:200] or None,
            )
            for r in trabalho.relatorios
            if r.status is not StatusFonte.DESATIVADA
        ]
        return precos, saude, chaves

    async def registrar(self, trabalho: TrabalhoBusca) -> None:
        precos, saude, chaves = self.linhas(trabalho)
        if not precos and not saude:
            return
        try:
            async with self._sessoes() as sessao, sessao.begin():
                sessao.add_all([*precos, *saude])
        except Exception:
            log.exception("falha ao gravar histórico")
            return
        for chave, total in chaves.items():
            self._gravados.guardar(chave, total)
        await self.expurgar_se_preciso()

    async def expurgar(self) -> int:
        limite = datetime.now(UTC) - timedelta(days=self._dias_retencao)
        async with self._sessoes() as sessao, sessao.begin():
            precos = await sessao.execute(
                delete(HistoricoPreco).where(HistoricoPreco.observado_em < limite)
            )
            saude = await sessao.execute(delete(SaudeLoja).where(SaudeLoja.observado_em < limite))
        return (precos.rowcount or 0) + (saude.rowcount or 0)

    async def expurgar_se_preciso(self) -> None:
        agora = self._relogio()
        if self._ultimo_expurgo is not None and agora - self._ultimo_expurgo < INTERVALO_EXPURGO_S:
            return
        self._ultimo_expurgo = agora
        try:
            apagadas = await self.expurgar()
        except Exception:
            log.exception("falha ao apagar histórico antigo")
            return
        if apagadas:
            log.info(
                "histórico: %d linhas com mais de %d dias apagadas", apagadas, self._dias_retencao
            )

    async def resumo_ofertas(self, ids: list[str], dias: int) -> dict[str, list[PontoDia]]:
        desde = datetime.now(UTC) - timedelta(days=dias)
        consulta = (
            select(HistoricoPreco.oferta, HistoricoPreco.observado_em, HistoricoPreco.preco)
            .where(
                HistoricoPreco.oferta.in_(ids[:OFERTAS_POR_CONSULTA]),
                HistoricoPreco.observado_em >= desde,
                # A atualização agendada lê sem CEP; misturar com a busca da pessoa
                # mudaria o habitual de lojas com preço regional.
                HistoricoPreco.agendada.is_(False),
            )
            .order_by(HistoricoPreco.observado_em)
            .limit(LINHAS_MAXIMAS_SERIE)
        )
        async with self._sessoes() as sessao:
            linhas = (await sessao.execute(consulta)).all()
        menores: dict[str, dict[date, int]] = {}
        for oferta, quando, preco in linhas:
            if oferta is None:
                continue
            dia = _com_fuso(quando).astimezone(HORARIO_DE_BRASILIA).date()
            por_dia = menores.setdefault(oferta, {})
            atual = por_dia.get(dia)
            por_dia[dia] = preco if atual is None else min(preco, atual)
        return {
            oferta: [PontoDia(dia, preco) for dia, preco in sorted(por_dia.items())]
            for oferta, por_dia in menores.items()
        }

    async def quedas(
        self, dias: int, limite: int, nomes_lojas: dict[str, str], agora: datetime | None = None
    ) -> PainelQuedas:
        return await self._quedas.obter_ou_carregar(
            (dias, limite),
            lambda: self._calcular_quedas(dias, limite, nomes_lojas, agora or datetime.now(UTC)),
        )

    async def _calcular_quedas(
        self, dias: int, limite: int, nomes_lojas: dict[str, str], agora: datetime
    ) -> PainelQuedas:
        h = HistoricoPreco
        recente = agora - timedelta(hours=HORAS_VISTA_RECENTE)
        # Só a série sem CEP: com CEP o preço pode mudar por região e criar quedas falsas.
        na_janela = (
            h.observado_em >= agora - timedelta(days=dias),
            h.prefixo_cep.is_(None),
            h.oferta.is_not(None),
        )
        # Filtro barato no banco: quem caiu 10% da mediana caiu 10% do maior preço da janela.
        candidatas = (
            select(h.oferta)
            .where(*na_janela)
            .group_by(h.oferta)
            .having(
                func.max(h.observado_em) >= recente,
                func.min(case((h.observado_em >= recente, h.preco))) * 10 <= func.max(h.preco) * 9,
            )
        )
        consulta = (
            select(h.id, h.oferta, h.observado_em, h.preco)
            .where(*na_janela, h.oferta.in_(candidatas))
            .order_by(h.oferta, h.observado_em, h.id)
        )
        async with self._sessoes() as sessao:
            linhas = (await sessao.execute(consulta)).all()

        hoje = agora.astimezone(HORARIO_DE_BRASILIA).date()
        achadas: dict[int, tuple] = {}
        for _, grupo in groupby(linhas, key=lambda linha: linha.oferta):
            pontos = list(grupo)
            ultimo = pontos[-1]
            visto_em = _com_fuso(ultimo.observado_em)
            if visto_em < recente:
                continue
            por_dia: dict[date, int] = {}
            for p in pontos:
                dia = _com_fuso(p.observado_em).astimezone(HORARIO_DE_BRASILIA).date()
                por_dia[dia] = min(p.preco, por_dia.get(dia, p.preco))
            passados = [preco for dia, preco in por_dia.items() if dia < hoje]
            if len(por_dia) < DIAS_MINIMOS_QUEDA or not passados:
                continue
            centro = statistics.median(passados)
            if ultimo.preco * 10 > centro * 9:
                continue
            achadas[ultimo.id] = (ultimo, centro, passados, len(por_dia), visto_em)

        detalhes = select(h.id, h.titulo, h.loja, h.link, h.imagem, h.preco_original).where(
            h.id.in_(list(achadas)), h.link.is_not(None)
        )
        async with self._sessoes() as sessao:
            gravadas = (await sessao.execute(detalhes)).all()
        itens = []
        for d in gravadas:
            ultimo, centro, passados, dias_observados, visto_em = achadas[d.id]
            itens.append(
                QuedaPreco(
                    oferta=ultimo.oferta,
                    titulo=d.titulo,
                    loja=Loja(d.loja, nomes_lojas.get(d.loja, d.loja)),
                    link=d.link,
                    imagem=d.imagem,
                    preco=ultimo.preco,
                    preco_original=d.preco_original,
                    mediana=round(centro),
                    menor=min(passados),
                    maior=max(passados),
                    dias_observados=dias_observados,
                    variacao=round(ultimo.preco / centro - 1, 4),
                    visto_em=instante_iso(visto_em),
                )
            )
        itens.sort(key=lambda i: (i.variacao, i.oferta))
        return PainelQuedas(dias, instante_iso(agora), itens[:limite])

    async def serie(self, produto: str, cep: str | None, dias: int) -> list[SerieLoja]:
        desde = datetime.now(UTC) - timedelta(days=dias)
        consulta = (
            select(HistoricoPreco)
            .where(HistoricoPreco.produto == produto, HistoricoPreco.observado_em >= desde)
            .order_by(HistoricoPreco.observado_em.desc(), HistoricoPreco.id.desc())
            .limit(LINHAS_MAXIMAS_SERIE)
        )
        if cep:
            consulta = consulta.where(HistoricoPreco.prefixo_cep == cep[:5])
        async with self._sessoes() as sessao:
            linhas = list(reversed((await sessao.scalars(consulta)).all()))

        por_loja: dict[tuple[str, str | None], list[HistoricoPreco]] = {}
        for linha in linhas:
            por_loja.setdefault((linha.loja, linha.vendedor), []).append(linha)
        saida = [
            SerieLoja(
                loja=loja,
                vendedor=vendedor,
                menor_total=min(r.total for r in pontos),
                atual=pontos[-1].total,
                pontos=[
                    Ponto(
                        em=_com_fuso(r.observado_em),
                        preco=r.preco,
                        preco_pix=r.preco_pix,
                        frete=r.frete,
                        total=r.total,
                        frete_exato=r.status_frete == StatusFrete.CALCULADO,
                    )
                    for r in pontos
                ],
            )
            for (loja, vendedor), pontos in por_loja.items()
        ]
        saida.sort(key=lambda s: s.atual)
        return saida


def _gravavel(o: Oferta) -> bool:
    return (
        0 < len(o.id) <= TAMANHO_MAXIMO_OFERTA
        and o.relevancia >= RELEVANCIA_MINIMA_HISTORICO
        and o.disponivel
        and o.frete.status is not StatusFrete.CALCULANDO
    )


def _com_fuso(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)
