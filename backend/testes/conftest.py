import json
from pathlib import Path

import httpx
import pytest
import respx

from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes.base import ContextoBusca
from app.modelos import Endereco
from app.relevancia import interpretar_consulta

GRAVACOES = Path(__file__).parent / "gravacoes"


def gravacao_json(nome: str):
    return json.loads((GRAVACOES / nome).read_text("utf-8"))


def gravacao_bytes(nome: str) -> bytes:
    return (GRAVACOES / nome).read_bytes()


def contexto(texto: str, cep: str | None = "30130010") -> ContextoBusca:
    endereco = Endereco(cep, None, None, "Belo Horizonte", "MG") if cep else None
    return ContextoBusca(texto, interpretar_consulta(texto), endereco)


@pytest.fixture
def config() -> Configuracoes:
    return Configuracoes(
        _env_file=None,
        segundos_limite_fonte=3,
        produtos_por_loja=30,
        cotacoes_por_loja=40,
        relevancia_minima_cotacao=50,
        aquecimento_auditoria_cotacao=0,
        taxa_auditoria_cotacao=0,
    )


@pytest.fixture
async def http(config: Configuracoes):
    async with ClienteHttp(config) as http:
        yield http


@pytest.fixture
def simulador():
    with respx.mock(assert_all_called=False) as roteador:
        yield roteador


def resposta_json(corpo, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=corpo)
