import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.banco import HistoricoPreco, SaudeLoja
from app.busca import TrabalhoBusca
from app.cache import CacheComValidade
from app.modelos import Oferta, StatusFonte, StatusFrete

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


class RegistroHistorico:
    def __init__(
        self, sessoes: async_sessionmaker, relogio=time.monotonic, dias_retencao: int = 180
    ):
        self._sessoes = sessoes
        self._relogio = relogio
        self._dias_retencao = dias_retencao
        self._ultimo_expurgo: float | None = None
        self._gravados: CacheComValidade[tuple, int] = CacheComValidade(
            SEGUNDOS_MESMO_PRECO, CHAVES_LEMBRADAS, relogio
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
