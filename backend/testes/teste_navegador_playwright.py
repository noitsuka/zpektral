import pytest

playwright = pytest.importorskip("playwright.async_api")

from app.navegador import playwright as modulo  # noqa: E402
from app.navegador.playwright import PaginaPlaywright  # noqa: E402


class PaginaQueNavega:
    def __init__(self, *respostas: str | Exception):
        self._respostas = list(respostas)

    async def content(self) -> str:
        resposta = self._respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture(autouse=True)
def sem_intervalo(monkeypatch):
    monkeypatch.setattr(modulo, "PASSO_AGUARDAR_S", 0)


async def teste_aguardar_tolera_a_pagina_no_meio_da_navegacao():
    pagina = PaginaQueNavega(playwright.Error("Execution context was destroyed"), "<p>pronto</p>")
    assert await PaginaPlaywright(pagina, 1000).aguardar(lambda html: "pronto" in html, 1000)


async def teste_aguardar_nao_esconde_erro_da_condicao():
    def condicao_com_defeito(html: str) -> bool:
        raise KeyError(html)

    pagina = PaginaQueNavega("<p></p>")
    with pytest.raises(KeyError):
        await PaginaPlaywright(pagina, 1000).aguardar(condicao_com_defeito, 1000)
