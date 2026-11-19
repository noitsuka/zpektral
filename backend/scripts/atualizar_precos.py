import argparse
import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.banco import HistoricoPreco, criar_motor, criar_sessoes
from app.busca import ServicoBusca, chave_cache
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes, obter_configuracoes
from app.fontes import Fonte, criar_fontes
from app.historico import RegistroHistorico

log = logging.getLogger("zpektral.atualizacao")

DIAS_POPULARIDADE = 7
# Uma hora de folga sobre o intervalo de 6 horas, porque o agendador do GitHub atrasa.
HORAS_TTL_MINIMO = 5
HORAS_TTL_MAXIMO = 48
ORCAMENTO_PADRAO = 20


@dataclass(slots=True)
class Estatistica:
    consulta: str
    buscas: int
    volatilidade: float
    atualizada_em: datetime | None

    @property
    def prioridade(self) -> float:
        return self.buscas * (1 + self.volatilidade)

    @property
    def validade(self) -> timedelta:
        horas = HORAS_TTL_MAXIMO / self.prioridade if self.prioridade else HORAS_TTL_MAXIMO
        return timedelta(hours=min(HORAS_TTL_MAXIMO, max(HORAS_TTL_MINIMO, horas)))


def escolher(estatisticas: Sequence[Estatistica], agora: datetime, orcamento: int) -> list[str]:
    vencidas = [
        e
        for e in estatisticas
        if e.buscas and (e.atualizada_em is None or agora - e.atualizada_em >= e.validade)
    ]
    vencidas.sort(key=lambda e: (-e.prioridade, e.consulta))
    return [e.consulta for e in vencidas[:orcamento]]


async def estatisticas(sessoes: async_sessionmaker, agora: datetime) -> list[Estatistica]:
    h = HistoricoPreco
    recentes = (
        h.observado_em >= agora - timedelta(days=DIAS_POPULARIDADE),
        h.consulta.is_not(None),
    )
    # Cada busca grava suas linhas numa transação, com o mesmo instante.
    resumo = (
        select(
            h.consulta,
            func.count(func.distinct(case((h.agendada.is_(False), h.observado_em)))),
            func.max(case((h.prefixo_cep.is_(None), h.observado_em))),
        )
        .where(*recentes)
        .group_by(h.consulta)
    )
    por_oferta = (
        select(h.consulta, func.count(func.distinct(h.preco)).label("precos"))
        .where(*recentes)
        .group_by(h.consulta, h.oferta)
        .subquery()
    )
    volatilidade = select(
        por_oferta.c.consulta, func.avg(case((por_oferta.c.precos > 1, 1.0), else_=0.0))
    ).group_by(por_oferta.c.consulta)
    async with sessoes() as sessao:
        linhas = (await sessao.execute(resumo)).all()
        volateis = dict((await sessao.execute(volatilidade)).all())

    por_chave: dict[str, Estatistica] = {}
    for consulta, buscas, atualizada_em in sorted(linhas, key=lambda linha: -linha[1]):
        quando = (
            atualizada_em.replace(tzinfo=atualizada_em.tzinfo or UTC) if atualizada_em else None
        )
        atual = Estatistica(consulta, buscas, float(volateis.get(consulta) or 0), quando)
        chave, _ = chave_cache(consulta, None)
        anterior = por_chave.setdefault(chave, atual)
        if anterior is not atual:
            anterior.buscas += atual.buscas
            anterior.volatilidade = max(anterior.volatilidade, atual.volatilidade)
            if quando and (anterior.atualizada_em is None or quando > anterior.atualizada_em):
                anterior.atualizada_em = quando
    return list(por_chave.values())


async def atualizar_precos(
    sessoes: async_sessionmaker,
    fontes: Sequence[Fonte],
    config: Configuracoes,
    orcamento: int,
    agora: datetime | None = None,
) -> list[str]:
    agora = agora or datetime.now(UTC)
    consultas = escolher(await estatisticas(sessoes, agora), agora, orcamento)
    if not consultas:
        return []
    registro = RegistroHistorico(sessoes, dias_retencao=config.dias_historico, agendada=True)
    await registro.lembrar_gravados_hoje(agora)
    servico = ServicoBusca(fontes, config, ao_concluir=registro.registrar)
    try:
        for consulta in consultas:
            trabalho, _ = servico.iniciar(consulta, None)
            await trabalho.gravado.wait()  # a busca conclui antes de gravar
    finally:
        await servico.encerrar()
    return consultas


async def executar(orcamento: int) -> None:
    config = obter_configuracoes()
    if not config.url_banco:
        raise SystemExit("defina DATABASE_URL para atualizar os preços")
    motor = criar_motor(config.url_banco)
    try:
        async with ClienteHttp(config) as http:
            feitas = await atualizar_precos(
                criar_sessoes(motor), criar_fontes(http, config), config, orcamento
            )
    finally:
        await motor.dispose()
    # Só a contagem: o texto das buscas não vai para o log público da CI.
    log.info("%d buscas atualizadas sem CEP (orçamento de %d)", len(feitas), orcamento)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refaz sem CEP as buscas mais feitas na última semana e grava o histórico."
    )
    parser.add_argument(
        "--orcamento",
        type=int,
        default=ORCAMENTO_PADRAO,
        help=f"máximo de buscas nesta execução (padrão {ORCAMENTO_PADRAO})",
    )
    argumentos = parser.parse_args()
    # cada busca consulta perto de 100 lojas; o teto protege as lojas e o banco
    if not 1 <= argumentos.orcamento <= 50:
        parser.error("o orçamento precisa ficar entre 1 e 50 buscas")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    log.setLevel(logging.INFO)
    asyncio.run(executar(argumentos.orcamento))


if __name__ == "__main__":
    main()
