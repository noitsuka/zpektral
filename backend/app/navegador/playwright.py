import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from app.configuracao import Configuracoes
from app.navegador.base import Estrategia, NavegadorIndisponivel, Pagina, Seletor

if TYPE_CHECKING:
    from playwright.async_api import Browser, Locator, Page, Playwright

log = logging.getLogger("zpektral.navegador")

ESPERA_POR_SELETOR_MS = 1500
PASSO_AGUARDAR_S = 0.25


class PaginaPlaywright:
    def __init__(self, pagina: "Page", tempo_limite_ms: int):
        self._pagina = pagina
        self._tempo_limite_ms = tempo_limite_ms

    def _localizar(self, s: Seletor) -> "Locator":
        p = self._pagina
        match s.estrategia:
            case Estrategia.CSS:
                return p.locator(s.valor).first
            case Estrategia.PAPEL:
                nome = re.compile(s.nome or ".*", re.I)
                return p.get_by_role(s.valor, name=nome).first  # type: ignore[arg-type]
            case Estrategia.ROTULO:
                return p.get_by_label(re.compile(s.valor, re.I)).first
            case Estrategia.PLACEHOLDER:
                return p.get_by_placeholder(re.compile(s.valor, re.I)).first
            case Estrategia.TEXTO:
                return p.get_by_text(re.compile(s.valor, re.I)).first

    async def _primeiro_visivel(
        self, seletores: Sequence[Seletor], tempo_ms: int
    ) -> "Locator | None":
        for s in seletores:
            local = self._localizar(s)
            try:
                if await local.is_visible():
                    return local
            except Exception:
                continue
        fim = time.monotonic() + tempo_ms / 1000
        for s in seletores:
            restante = int((fim - time.monotonic()) * 1000)
            if restante <= 0:
                break
            local = self._localizar(s)
            try:
                await local.wait_for(state="visible", timeout=min(restante, ESPERA_POR_SELETOR_MS))
                return local
            except Exception:
                continue
        return None

    async def abrir(self, url: str) -> None:
        await self._pagina.goto(url, wait_until="domcontentloaded", timeout=self._tempo_limite_ms)

    async def html(self) -> str:
        return await self._pagina.content()

    async def texto(self) -> str:
        return await self._pagina.inner_text("body")

    async def url(self) -> str:
        return self._pagina.url

    async def clicar(self, seletores: Sequence[Seletor]) -> bool:
        local = await self._primeiro_visivel(seletores, self._tempo_limite_ms // 3)
        if local is None:
            return False
        await local.click(timeout=self._tempo_limite_ms)
        return True

    async def preencher(self, seletores: Sequence[Seletor], valor: str) -> bool:
        local = await self._primeiro_visivel(seletores, self._tempo_limite_ms // 3)
        if local is None:
            return False
        await local.fill(valor, timeout=self._tempo_limite_ms)
        return True

    async def esperar(self, seletores: Sequence[Seletor], tempo_ms: int) -> bool:
        return await self._primeiro_visivel(seletores, tempo_ms) is not None

    async def aguardar(self, condicao: Callable[[str], bool], tempo_ms: int) -> bool:
        fim = time.monotonic() + tempo_ms / 1000
        while True:
            try:
                if condicao(await self._pagina.content()):
                    return True
            except Exception:
                pass
            if time.monotonic() >= fim:
                return False
            await asyncio.sleep(PASSO_AGUARDAR_S)


class NavegadorPlaywright:
    def __init__(self, config: Configuracoes):
        self._config = config
        self._trava = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._falha: str | None = None

    async def _garantir(self) -> "Browser":
        if self._browser is not None:
            return self._browser
        if self._falha is not None:
            raise NavegadorIndisponivel(self._falha)
        async with self._trava:
            if self._browser is not None:
                return self._browser
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                self._falha = "pacote playwright não instalado (pip install .[navegador])"
                raise NavegadorIndisponivel(self._falha) from None
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
            except Exception as excecao:
                self._falha = f"não foi possível abrir o Chromium: {type(excecao).__name__}"
                log.warning("%s (rode: playwright install chromium)", self._falha)
                await self.fechar()
                raise NavegadorIndisponivel(self._falha) from excecao
            return self._browser

    @asynccontextmanager
    async def pagina(self) -> AsyncIterator[Pagina]:
        browser = await self._garantir()
        contexto: Any = await browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
        try:
            pagina = await contexto.new_page()
            yield PaginaPlaywright(pagina, self._config.navegador_tempo_limite_ms)
        finally:
            await contexto.close()

    async def fechar(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
