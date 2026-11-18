import httpx
import pytest

from app.configuracao import Configuracoes
from app.fontes.vtex import carregar_lojas
from scripts.sondar_lojas_vtex import CAMINHOS, proibido_pelo_robots

pytestmark = pytest.mark.live

INTELIGENTE, LEGADA, SIMULACAO = CAMINHOS
USADOS = {
    "is": {INTELIGENTE, SIMULACAO},
    "legacy": {LEGADA, SIMULACAO},
    "auto": {INTELIGENTE, LEGADA, SIMULACAO},
}


async def teste_nenhuma_loja_cadastrada_proibe_as_apis_no_robots():
    agente = Configuracoes(_env_file=None).agente_usuario
    proibidas = {}
    async with httpx.AsyncClient(timeout=15, headers={"user-agent": agente}) as cliente:
        for loja in carregar_lojas():
            resposta = await cliente.get(f"https://{loja.dominio}/robots.txt")
            if resposta.status_code != 200:
                continue
            if caminhos := USADOS[loja.busca] & set(proibido_pelo_robots(resposta.text)):
                proibidas[loja.id] = sorted(caminhos)
    assert not proibidas, f"tire do cadastro: {proibidas}"
