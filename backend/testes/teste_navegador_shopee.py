from datetime import date

import pytest

from app.navegador.base import Estrategia, StatusCotacao
from app.navegador.shopee import (
    SELETORES,
    FreteShopeeNavegador,
    detectar_bloqueio,
    ler_frete,
    url_do_produto,
)
from testes.pagina_falsa import IntervaloImediato, NavegadorFalso, PaginaFalsa

HOJE = date(2026, 10, 27)

PRODUTO = (
    "<html><body><div><h1>Fone Bluetooth JBL Tune 520BT</h1></div>"
    "<div>R$ 199,90</div>"
    '<div><button aria-label="Alterar CEP de entrega">Enviar para São Paulo</button></div>'
    "</body></html>"
)
PRODUTO_SEM_ROTULO = PRODUTO.replace(' aria-label="Alterar CEP de entrega"', "")
MODAL = '<div role="dialog"><input placeholder="Digite seu CEP"><button>Confirmar</button></div>'
COTADO = (
    "<html><body><div><h1>Fone Bluetooth JBL Tune 520BT</h1></div>"
    "<div>Envio para 01310-100</div><div>Frete R$ 12,90</div>"
    "<div>Chega entre 30 out - 4 nov</div></body></html>"
)


def teste_frete_gratis_com_prazo():
    cotacao = ler_frete("Envio para 01310-100\nFrete grátis\nReceba até 5 de nov", HOJE)
    assert cotacao.status is StatusCotacao.COTADO
    assert cotacao.valor == 0 and cotacao.gratis
    assert cotacao.prazo_dias == 9 and cotacao.entrega_ate == "2026-11-05"


def teste_frete_pago_usa_a_ultima_data_do_intervalo():
    cotacao = ler_frete("Frete R$ 12,90\nChega entre 30 out - 4 nov", HOJE)
    assert cotacao.status is StatusCotacao.COTADO
    assert cotacao.valor == 1290
    assert cotacao.entrega_ate == "2026-11-04"


def teste_frete_gratis_com_condicao_nao_vira_gratis():
    cotacao = ler_frete("Frete grátis em pedidos acima de R$ 19,00\nReceba até 5 de nov", HOJE)
    assert cotacao.status is StatusCotacao.SEM_INFORMACAO
    assert cotacao.prazo_dias == 9


@pytest.mark.parametrize(
    ("conteudo", "status"),
    [
        ("Produto esgotado", StatusCotacao.INDISPONIVEL),
        ("CEP inválido. Confira e tente de novo", StatusCotacao.CEP_REJEITADO),
        ("Não entrega para o seu CEP", StatusCotacao.NAO_ENTREGA),
        ("Fone JBL R$ 199,90", StatusCotacao.SEM_INFORMACAO),
    ],
)
def teste_situacoes_da_pagina(conteudo, status):
    assert ler_frete(conteudo, HOJE).status is status


def teste_challenge_e_login():
    produto = url_do_produto(77, 1)
    assert detectar_bloqueio("", "https://shopee.com.br/verify/traffic?x=1").status is (  # type: ignore[union-attr]
        StatusCotacao.DESAFIO
    )
    assert detectar_bloqueio("Complete o captcha", produto).status is StatusCotacao.DESAFIO  # type: ignore[union-attr]
    assert detectar_bloqueio("", "https://shopee.com.br/buyer/login?next=x").status is (  # type: ignore[union-attr]
        StatusCotacao.LOGIN
    )
    assert detectar_bloqueio("Fone R$ 199,90", produto) is None


def _fluxo(pagina_inicial: str, depois: str = COTADO, url_final=None):
    def ao_clicar(pagina: PaginaFalsa, seletor):
        if seletor in SELETORES.abrir_local:
            pagina.atual = pagina.atual + MODAL
        elif seletor in SELETORES.confirmar:
            pagina.atual = depois
            pagina.paginas["*"] = depois

    pagina = PaginaFalsa({"*": pagina_inicial}, ao_clicar=ao_clicar, url_final=url_final)
    provedor = FreteShopeeNavegador(
        NavegadorFalso(pagina), _config(), hoje=lambda: HOJE, intervalo=IntervaloImediato()
    )
    return pagina, provedor


def _config():
    from app.configuracao import Configuracoes

    return Configuracoes(_env_file=None)  # type: ignore[call-arg]


async def teste_fluxo_informa_o_cep_e_le_o_frete():
    pagina, provedor = _fluxo(PRODUTO)
    destino = {}
    await provedor.cotar([("shopee:1", 77, 1), ("shopee:2", 77, 2)], "01310100", destino)
    assert destino["shopee:1"].status is StatusCotacao.COTADO
    assert destino["shopee:1"].valor == 1290
    assert destino["shopee:2"].status is StatusCotacao.COTADO
    assert pagina.abertas == [url_do_produto(77, 1), url_do_produto(77, 2)]
    assert sum(1 for s in pagina.cliques if s in SELETORES.abrir_local) == 1
    assert [v for _, v in pagina.preenchidos] == ["01310-100"]


async def teste_fallback_pelo_papel_e_nome_do_botao():
    pagina, provedor = _fluxo(PRODUTO_SEM_ROTULO)
    destino = {}
    await provedor.cotar([("shopee:1", 77, 1)], "01310100", destino)
    assert destino["shopee:1"].status is StatusCotacao.COTADO
    assert pagina.cliques[0].estrategia is Estrategia.PAPEL


async def teste_challenge_encerra_sem_interagir():
    pagina, provedor = _fluxo(
        "<html></html>", url_final=lambda _: "https://shopee.com.br/verify/traffic"
    )
    destino = {}
    await provedor.cotar([("shopee:1", 77, 1), ("shopee:2", 77, 2)], "01310100", destino)
    assert destino["shopee:1"].status is StatusCotacao.DESAFIO
    assert destino["shopee:2"].status is StatusCotacao.INTERROMPIDO
    assert not pagina.cliques and not pagina.preenchidos and len(pagina.abertas) == 1


async def teste_login_obrigatorio_encerra():
    _pagina, provedor = _fluxo(
        "<html></html>", url_final=lambda _: "https://shopee.com.br/buyer/login?next=x"
    )
    destino = {}
    await provedor.cotar([("shopee:1", 77, 1)], "01310100", destino)
    assert destino["shopee:1"].status is StatusCotacao.LOGIN


async def teste_sem_seletor_de_cep():
    _pagina, provedor = _fluxo("<html><body><div>Fone JBL R$ 199,90</div></body></html>")
    destino = {}
    await provedor.cotar([("shopee:1", 77, 1), ("shopee:2", 77, 2)], "01310100", destino)
    assert destino["shopee:1"].status is StatusCotacao.SEM_SELETOR
    assert destino["shopee:2"].status is StatusCotacao.INTERROMPIDO


@pytest.mark.skip(reason="browser execution unavailable in current environment")
async def teste_ao_vivo_frete_shopee_com_playwright():
    from app.navegador.playwright import NavegadorPlaywright

    config = _config()
    navegador = NavegadorPlaywright(config)
    destino = {}
    try:
        await FreteShopeeNavegador(navegador, config).cotar(
            [("shopee:1", 1, 1)], "01310100", destino
        )
    finally:
        await navegador.fechar()
    assert destino
