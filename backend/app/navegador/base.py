import asyncio
import re
import time
import unicodedata
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol

from app.modelos import Frete, StatusFrete


class NavegadorIndisponivel(Exception):
    pass


class Estrategia(StrEnum):
    CSS = "css"
    PAPEL = "papel"
    ROTULO = "rotulo"
    PLACEHOLDER = "placeholder"
    TEXTO = "texto"


@dataclass(frozen=True)
class Seletor:
    estrategia: Estrategia
    valor: str
    nome: str | None = None


def css(valor: str) -> Seletor:
    return Seletor(Estrategia.CSS, valor)


def papel(valor: str, nome: str) -> Seletor:
    return Seletor(Estrategia.PAPEL, valor, nome)


def rotulo(padrao: str) -> Seletor:
    return Seletor(Estrategia.ROTULO, padrao)


def placeholder(padrao: str) -> Seletor:
    return Seletor(Estrategia.PLACEHOLDER, padrao)


def texto(padrao: str) -> Seletor:
    return Seletor(Estrategia.TEXTO, padrao)


class StatusCotacao(StrEnum):
    COTADO = "cotado"
    DESAFIO = "automation_challenge"
    LOGIN = "login_required"
    CEP_REJEITADO = "cep_rejeitado"
    CEP_NAO_APLICADO = "cep_nao_aplicado"
    INDISPONIVEL = "indisponivel"
    NAO_ENTREGA = "nao_entrega"
    SEM_INFORMACAO = "sem_informacao"
    SEM_SELETOR = "seletor_nao_encontrado"
    INTERROMPIDO = "interrompido"


BLOQUEIOS = {StatusCotacao.DESAFIO, StatusCotacao.LOGIN}


@dataclass(frozen=True)
class CotacaoNavegador:
    status: StatusCotacao
    valor: int | None = None
    gratis: bool = False
    prazo: str | None = None
    prazo_dias: float | None = None
    entrega_ate: str | None = None
    modalidade: str | None = None
    detalhe: str | None = None

    def para_frete(self) -> Frete | None:
        if self.status is StatusCotacao.NAO_ENTREGA:
            return Frete(StatusFrete.NAO_ENTREGA)
        if self.status is not StatusCotacao.COTADO or self.valor is None:
            return None
        return Frete(
            StatusFrete.CALCULADO,
            valor=self.valor,
            prazo=self.prazo,
            prazo_dias=self.prazo_dias,
            modalidade=self.modalidade,
            entrega_ate=self.entrega_ate,
            cotado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        )


class Pagina(Protocol):
    async def abrir(self, url: str) -> None: ...

    async def html(self) -> str: ...

    async def texto(self) -> str: ...

    async def url(self) -> str: ...

    async def clicar(self, seletores: Sequence[Seletor]) -> bool: ...

    async def preencher(self, seletores: Sequence[Seletor], valor: str) -> bool: ...

    async def esperar(self, seletores: Sequence[Seletor], tempo_ms: int) -> bool: ...

    async def aguardar(self, condicao: Callable[[str], bool], tempo_ms: int) -> bool: ...


class Navegador(Protocol):
    def pagina(self) -> AbstractAsyncContextManager[Pagina]: ...


class Intervalo:
    def __init__(self, segundos: float, relogio: Callable[[], float] = time.monotonic):
        self._segundos = segundos
        self._relogio = relogio
        self._ultimo: float | None = None
        self._trava = asyncio.Lock()

    async def aguardar(self) -> None:
        async with self._trava:
            if self._ultimo is not None:
                falta = self._segundos - (self._relogio() - self._ultimo)
                if falta > 0:
                    await asyncio.sleep(falta)
            self._ultimo = self._relogio()


MESES = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}
_DATA_POR_EXTENSO = re.compile(r"(\d{1,2})\s+de\s+([a-zç]{3})[a-zç]*\.?")
_DATA_NUMERICA = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
_DIA_E_MES = re.compile(r"(\d{1,2})\s+([a-zç]{3})[a-zç]*\.?(?=\s|$|[,.)])")


def sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _data_valida(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _proxima(dia: int, mes: int, hoje: date) -> date | None:
    candidata = _data_valida(hoje.year, mes, dia)
    if candidata is not None and candidata < hoje:
        candidata = _data_valida(hoje.year + 1, mes, dia)
    return candidata


def ler_data_de_entrega(bruto: str | None, hoje: date) -> date | None:
    if not bruto:
        return None
    texto = sem_acentos(bruto).lower()
    if "hoje" in texto:
        return hoje
    if "amanha" in texto:
        return date.fromordinal(hoje.toordinal() + 1)
    datas: list[date] = []
    for dia, mes in _DATA_POR_EXTENSO.findall(texto):
        if mes[:3] in MESES and (d := _proxima(int(dia), MESES[mes[:3]], hoje)):
            datas.append(d)
    if not datas:
        for dia, mes in _DIA_E_MES.findall(texto):
            if mes[:3] in MESES and (d := _proxima(int(dia), MESES[mes[:3]], hoje)):
                datas.append(d)
    if not datas:
        for dia, mes, ano in _DATA_NUMERICA.findall(texto):
            if ano:
                ano_cheio = int(ano) + (2000 if len(ano) == 2 else 0)
                d = _data_valida(ano_cheio, int(mes), int(dia))
            else:
                d = _proxima(int(dia), int(mes), hoje)
            if d is not None:
                datas.append(d)
    return max(datas) if datas else None


def prazo_ate(entrega: date | None, hoje: date) -> tuple[str | None, float | None, str | None]:
    if entrega is None:
        return None, None, None
    dias = max(0, (entrega - hoje).days)
    prazo = "hoje" if dias == 0 else f"até {dias} dia" if dias == 1 else f"até {dias} dias"
    return prazo, float(dias), entrega.isoformat()


def digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)
