import asyncio
import html
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit

from app.agrupamento import (
    atribuir_grupos,
    chave_propria,
    marcar_fora_da_curva,
    normalizar_ean,
    rebaixar_muito_abaixo,
)
from app.cache import CacheComValidade
from app.configuracao import Configuracoes
from app.fontes.base import ContextoBusca, Fonte
from app.modelos import Endereco, Frete, Oferta, RelatorioFonte, StatusFonte
from app.relevancia import interpretar_consulta, normalizar, texto_para_lojas
from app.saude import PainelSaude

log = logging.getLogger("zpektral.busca")

SEGUNDOS_TRABALHO_FALHO = 15
PRECO_MAXIMO_CENTAVOS = 100_000_000
TITULO_MAXIMO = 300
URL_MAXIMA = 2048
_TAG_HTML = re.compile(r"<[^>]{0,200}>")
CARACTERES_CONTROLE = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


class Fase(StrEnum):
    CATALOGO = "catalogo"
    FINAL = "final"


@dataclass(slots=True)
class Lote:
    relatorio: RelatorioFonte
    ofertas: list[Oferta]
    fase: Fase


@dataclass(slots=True)
class TrabalhoBusca:
    consulta: str
    endereco: Endereco | None
    esperadas: list[str] = field(default_factory=list)
    lotes: list[Lote] = field(default_factory=list)
    definitivo: dict[str, Lote] = field(default_factory=dict)
    previa: dict[str, list[Oferta]] = field(default_factory=dict)
    inicio: float = field(default_factory=time.monotonic)
    tempo_decorrido_ms: int = 0
    concluido: asyncio.Event = field(default_factory=asyncio.Event)
    _mudou: asyncio.Event = field(default_factory=asyncio.Event)
    _versao: int = 0
    _agrupado: int = -1

    def adicionar(self, lote: Lote) -> None:
        self.lotes.append(lote)
        if lote.fase is Fase.FINAL:
            self.definitivo[lote.relatorio.id] = lote
            self.previa.pop(lote.relatorio.id, None)
        else:
            self.previa[lote.relatorio.id] = lote.ofertas
        self._versao += 1
        self._acordar()

    def concluir(self) -> None:
        self.tempo_decorrido_ms = round((time.monotonic() - self.inicio) * 1000)
        self.concluido.set()
        self._acordar()

    def _acordar(self) -> None:
        mudou, self._mudou = self._mudou, asyncio.Event()
        mudou.set()

    async def acompanhar(self) -> AsyncIterator[Lote]:
        enviado = 0
        while True:
            mudou = self._mudou
            while enviado < len(self.lotes):
                yield self.lotes[enviado]
                enviado += 1
            if self.concluido.is_set():
                return
            await mudou.wait()

    async def aguardar(self, segundos: float | None = None) -> bool:
        try:
            await asyncio.wait_for(self.concluido.wait(), segundos)
        except TimeoutError:
            return False
        return True

    @property
    def terminou(self) -> bool:
        return self.concluido.is_set()

    @property
    def ofertas(self) -> list[Oferta]:
        saida = [o for b in self.definitivo.values() for o in b.ofertas]
        saida.extend(o for ofertas in self.previa.values() for o in ofertas)
        return saida

    @property
    def relatorios(self) -> list[RelatorioFonte]:
        return [b.relatorio for b in self.definitivo.values()]

    @property
    def pendentes(self) -> list[str]:
        return [id_fonte for id_fonte in self.esperadas if id_fonte not in self.definitivo]

    def ofertas_agrupadas(self) -> list[Oferta]:
        ofertas = self.ofertas
        if self._agrupado != self._versao:
            atribuir_grupos(ofertas)
            marcar_fora_da_curva(ofertas)
            rebaixar_muito_abaixo(ofertas)
            self._agrupado = self._versao
        return ofertas


def chave_cache(consulta: str, endereco: Endereco | None) -> tuple[str, str]:
    chave = " ".join(normalizar(texto_para_lojas(consulta)).split())
    return chave, endereco.cep if endereco else ""


def limpar_titulo(bruto: str) -> str:
    texto = _TAG_HTML.sub(" ", html.unescape(bruto))
    texto = CARACTERES_CONTROLE.sub("", texto)
    return " ".join(texto.split())[:TITULO_MAXIMO]


def url_segura(bruto: object) -> str | None:
    if not isinstance(bruto, str) or not bruto or len(bruto) > URL_MAXIMA:
        return None
    try:
        partes = urlsplit(bruto.strip())
    except ValueError:
        return None
    if partes.scheme != "https" or not partes.netloc:
        return None
    return bruto.strip()


def sanear(ofertas: list[Oferta]) -> list[Oferta]:
    vistos: set[str] = set()
    saida = []
    for o in ofertas:
        if not isinstance(o.titulo, str) or not isinstance(o.preco, int):
            continue
        o.titulo = limpar_titulo(o.titulo)
        o.link = url_segura(o.link) or ""
        o.link_carrinho = url_segura(o.link_carrinho)
        o.imagem = url_segura(o.imagem)
        o.ean = normalizar_ean(o.ean)
        if o.id in vistos or not 0 < o.preco <= PRECO_MAXIMO_CENTAVOS or not o.titulo or not o.link:
            continue
        if o.frete.valor is not None and o.frete.valor < 0:
            o.frete = Frete.desconhecido()
            o.consolidar()
        if o.grupo is None:
            o.grupo = chave_propria(o)
        vistos.add(o.id)
        saida.append(o)
    return saida


class ServicoBusca:
    def __init__(
        self,
        fontes: Sequence[Fonte],
        config: Configuracoes,
        saude: PainelSaude | None = None,
        ao_concluir: Callable[[TrabalhoBusca], Awaitable[None]] | None = None,
    ):
        self.fontes = list(fontes)
        self._ao_concluir = ao_concluir
        self.saude = saude if saude is not None else PainelSaude()
        self._config = config
        self._trabalhos: CacheComValidade[tuple[str, str], TrabalhoBusca] = CacheComValidade(
            config.segundos_cache_busca, config.entradas_cache_busca
        )
        self._em_execucao: set[asyncio.Task[None]] = set()

    def em_cache(self, consulta: str, endereco: Endereco | None) -> bool:
        return self._trabalhos.obter(chave_cache(consulta, endereco)) is not None

    async def encerrar(self) -> None:
        tarefas = list(self._em_execucao)
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)

    @property
    def em_andamento(self) -> int:
        return len(self._em_execucao)

    def iniciar(self, consulta: str, endereco: Endereco | None) -> tuple[TrabalhoBusca, bool]:
        chave = chave_cache(consulta, endereco)
        trabalho = self._trabalhos.obter(chave)
        if trabalho is not None:
            return trabalho, True
        trabalho = TrabalhoBusca(consulta, endereco, esperadas=[s.id for s in self.fontes])
        self._trabalhos.guardar(chave, trabalho)
        tarefa = asyncio.create_task(self._executar(trabalho, chave))
        self._em_execucao.add(tarefa)
        tarefa.add_done_callback(self._em_execucao.discard)
        return trabalho, False

    async def _executar(self, trabalho: TrabalhoBusca, chave: tuple[str, str]) -> None:
        ctx = ContextoBusca(
            texto_para_lojas(trabalho.consulta),
            interpretar_consulta(trabalho.consulta),
            trabalho.endereco,
        )
        ativas = [s for s in self.fontes if s.ativa]
        for fonte in self.fontes:
            if not fonte.ativa:
                relatorio = RelatorioFonte(
                    fonte.id,
                    fonte.nome,
                    StatusFonte.DESATIVADA,
                    mensagem="credenciais não configuradas",
                )
                self.saude.registrar(relatorio)
                trabalho.adicionar(Lote(relatorio, [], Fase.FINAL))
        try:
            resultados = await asyncio.gather(
                *(self._executar_fonte(s, ctx, trabalho) for s in ativas), return_exceptions=True
            )
            for fonte, resultado in zip(ativas, resultados, strict=True):
                if isinstance(resultado, Exception):
                    log.error("execução de %s falhou: %r", fonte.id, resultado)
        finally:
            trabalho.concluir()
        if ativas and not any(
            b.relatorio.status is StatusFonte.OK for b in trabalho.definitivo.values()
        ):
            self._trabalhos.guardar(chave, trabalho, validade=SEGUNDOS_TRABALHO_FALHO)
        if self._ao_concluir is not None:
            await self._ao_concluir(trabalho)

    async def _executar_fonte(
        self, fonte: Fonte, ctx: ContextoBusca, trabalho: TrabalhoBusca
    ) -> None:
        inicio = time.monotonic()

        def previa(ofertas: list[Oferta]) -> None:
            decorrido = round((time.monotonic() - inicio) * 1000)
            relatorio = RelatorioFonte(
                fonte.id, fonte.nome, StatusFonte.OK, decorrido, len(ofertas)
            )
            trabalho.adicionar(Lote(relatorio, sanear(ofertas), Fase.CATALOGO))

        status, mensagem, ofertas = StatusFonte.OK, None, []
        try:
            ofertas = await asyncio.wait_for(
                fonte.buscar(ctx, previa), timeout=self._config.segundos_limite_fonte
            )
        except TimeoutError:
            status, mensagem = StatusFonte.TEMPO_ESGOTADO, "a loja demorou demais para responder"
        except Exception as excecao:
            log.warning("fonte %s falhou: %s", fonte.id, excecao)
            status, mensagem = StatusFonte.ERRO, "a loja não respondeu como esperado"
        ofertas = sanear(ofertas)
        decorrido = round((time.monotonic() - inicio) * 1000)
        relatorio = RelatorioFonte(fonte.id, fonte.nome, status, decorrido, len(ofertas), mensagem)
        self.saude.registrar(relatorio)
        trabalho.adicionar(Lote(relatorio, ofertas, Fase.FINAL))
