import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from app.cliente_http import ClienteHttp, ErroExterno
from app.modelos import RelatorioFonte, StatusFonte

log = logging.getLogger("zpektral.saude")

JANELA = 20
FALHAS_PARA_DEGRADAR = 3


class EstadoSaude(StrEnum):
    SAUDAVEL = "saudavel"
    DEGRADADA = "degradada"
    DESATIVADA = "desativada"
    NAO_INFORMADO = "sem_dados"


@dataclass(slots=True)
class SaudeFonte:
    id: str
    nome: str
    estado: EstadoSaude = EstadoSaude.NAO_INFORMADO
    falhas_seguidas: int = 0
    taxa_sucesso: float | None = None
    tempo_medio_ms: int | None = None
    ultimo_erro: str | None = None
    ultimo_sucesso: float | None = None


class PainelSaude:
    def __init__(self, http: ClienteHttp | None = None, url_webhook: str = ""):
        self._http = http
        self._webhook = url_webhook
        self._fontes: dict[str, SaudeFonte] = {}
        self._recentes: dict[str, deque[tuple[bool, int]]] = {}
        self._pendentes: set[asyncio.Task[None]] = set()

    def registrar(self, relatorio: RelatorioFonte) -> None:
        h = self._fontes.setdefault(relatorio.id, SaudeFonte(relatorio.id, relatorio.nome))
        if relatorio.status is StatusFonte.DESATIVADA:
            h.estado = EstadoSaude.DESATIVADA
            return
        aceitos = relatorio.status is StatusFonte.OK
        recentes = self._recentes.setdefault(relatorio.id, deque(maxlen=JANELA))
        recentes.append((aceitos, relatorio.tempo_ms))
        h.taxa_sucesso = round(sum(r[0] for r in recentes) / len(recentes), 3)
        tempos = [ms for boa, ms in recentes if boa]
        h.tempo_medio_ms = round(sum(tempos) / len(tempos)) if tempos else None
        antes = h.estado
        if aceitos:
            h.falhas_seguidas = 0
            h.ultimo_sucesso = time.time()
            h.estado = EstadoSaude.SAUDAVEL
        else:
            h.falhas_seguidas += 1
            h.ultimo_erro = relatorio.mensagem
            if h.falhas_seguidas >= FALHAS_PARA_DEGRADAR:
                h.estado = EstadoSaude.DEGRADADA
        if antes is not h.estado and EstadoSaude.DEGRADADA in (antes, h.estado):
            self._avisar(h, recuperou=h.estado is EstadoSaude.SAUDAVEL)

    def retrato(self) -> dict[str, SaudeFonte]:
        return dict(self._fontes)

    def _avisar(self, h: SaudeFonte, *, recuperou: bool) -> None:
        if recuperou:
            texto = f"zpektral: {h.nome} voltou a responder."
        else:
            texto = (
                f"zpektral: {h.nome} falhou {h.falhas_seguidas} vezes seguidas ({h.ultimo_erro})."
            )
        log.warning(texto)
        if not (self._webhook and self._http):
            return
        tarefa = asyncio.create_task(self._postar(texto))
        self._pendentes.add(tarefa)
        tarefa.add_done_callback(self._pendentes.discard)

    async def _postar(self, texto: str) -> None:
        if self._http is None:
            return
        try:
            corpo = {"content": texto, "text": texto}
            await self._http.requisitar(
                "POST", self._webhook, tentativas=0, aceitos=(200, 204), json=corpo
            )
        except ErroExterno as excecao:
            log.warning("webhook de alerta falhou: %s", excecao)
