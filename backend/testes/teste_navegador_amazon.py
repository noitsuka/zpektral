from datetime import date

import pytest

from app.modelos import StatusFrete
from app.navegador.amazon import (
    SELETORES,
    FreteAmazonNavegador,
    cep_aplicado,
    cep_rejeitado,
    detectar_bloqueio,
    ler_entrega,
    local_atual,
    url_do_produto,
)
from app.navegador.base import Estrategia, StatusCotacao
from testes.conftest import gravacao_bytes
from testes.pagina_falsa import IntervaloImediato, NavegadorFalso, PaginaFalsa

HOJE = date(2026, 10, 27)
BASE = gravacao_bytes("amazon_produto_sem_cep.html").decode("utf-8")
MODAL = (
    '<div id="GLUXModal"><input id="GLUXZipUpdateInput_0" maxlength="5">'
    '<input id="GLUXZipUpdateInput_1" maxlength="3">'
    '<span id="GLUXZipUpdate"><input type="submit"></span>'
    '<div id="GLUXZipError" class="a-hidden"></div></div>'
)
MODAL_COM_ERRO = MODAL.replace(
    '<div id="GLUXZipError" class="a-hidden"></div>',
    '<div id="GLUXZipError" class="a-box"><div>Digite um CEP válido</div></div>',
)


def variante(
    html: str = BASE,
    *,
    cep: str | None = "01310100",
    preco: str = "GRÁTIS",
    condicao: str = "no seu primeiro pedido",
    subtipo: str = "CONDITIONALLY_FREE",
    quando: str = "Amanhã, 28 de Outubro",
    disponibilidade: str | None = None,
) -> str:
    saida = (
        html.replace('data-csa-c-delivery-price="GRÁTIS"', f'data-csa-c-delivery-price="{preco}"')
        .replace(
            'data-csa-c-delivery-condition="no seu primeiro pedido"',
            f'data-csa-c-delivery-condition="{condicao}"',
        )
        .replace(
            'data-csa-c-mir-sub-type="CONDITIONALLY_FREE"', f'data-csa-c-mir-sub-type="{subtipo}"'
        )
        .replace(
            'data-csa-c-delivery-time="Amanhã, 28 de Outubro"',
            f'data-csa-c-delivery-time="{quando}"',
        )
    )
    if cep:
        saida = saida.replace("Bela Vista, 01319900", f"São Paulo, {cep}").replace(
            "Bela Vista 01319900", f"São Paulo {cep}"
        )
    if disponibilidade:
        saida = saida.replace(" Em estoque ", f" {disponibilidade} ")
    return saida


PAGO = variante(preco="R$ 19,90", condicao="", subtipo="PAID", quando="quinta-feira, 30 de outubro")
GRATIS = variante(condicao="", subtipo="FREE")


def teste_le_a_pagina_real_sem_cep():
    assert "01319900" in local_atual(BASE)
    assert not cep_aplicado(BASE, "01310-100")
    assert cep_aplicado(BASE, "01319-900")
    cotacao = ler_entrega(BASE, HOJE)
    assert cotacao.status is StatusCotacao.SEM_INFORMACAO
    assert cotacao.prazo_dias == 1
    assert "primeiro pedido" in (cotacao.detalhe or "")
    assert cotacao.para_frete() is None


def teste_frete_pago_com_prazo():
    cotacao = ler_entrega(PAGO, HOJE)
    assert cotacao.status is StatusCotacao.COTADO
    assert cotacao.valor == 1990 and not cotacao.gratis
    assert cotacao.prazo_dias == 3
    assert cotacao.entrega_ate == "2026-10-30"
    frete = cotacao.para_frete()
    assert frete is not None and frete.status is StatusFrete.CALCULADO and frete.valor == 1990


def teste_frete_gratis_sem_condicao():
    cotacao = ler_entrega(GRATIS, HOJE)
    assert cotacao.status is StatusCotacao.COTADO
    assert cotacao.valor == 0 and cotacao.gratis
    assert cotacao.prazo == "até 1 dia"


def teste_produto_indisponivel():
    cotacao = ler_entrega(variante(disponibilidade="Não disponível."), HOJE)
    assert cotacao.status is StatusCotacao.INDISPONIVEL


def teste_sem_entrega_no_cep():
    html = PAGO.replace(
        '<div id="mir-layout-DELIVERY_BLOCK">',
        '<div id="mir-layout-DELIVERY_BLOCK"><span>Este item não pode ser enviado '
        "para o local selecionado.</span>",
    )
    cotacao = ler_entrega(html, HOJE)
    assert cotacao.status is StatusCotacao.NAO_ENTREGA
    frete = cotacao.para_frete()
    assert frete is not None and frete.status is StatusFrete.NAO_ENTREGA


def teste_challenge_e_login_sao_detectados():
    captcha = '<form method="get" action="/errors/validateCaptcha"></form>'
    bloqueio = detectar_bloqueio(captcha, url_do_produto("B0CP6CVJSG"))
    assert bloqueio is not None and bloqueio.status is StatusCotacao.DESAFIO
    assert bloqueio.status.value == "automation_challenge"
    login = detectar_bloqueio("<html></html>", "https://www.amazon.com.br/ap/signin?x=1")
    assert login is not None and login.status is StatusCotacao.LOGIN
    assert detectar_bloqueio(BASE, url_do_produto("B0CP6CVJSG")) is None


def teste_erro_de_cep_so_conta_quando_visivel():
    assert not cep_rejeitado(BASE + MODAL)
    assert cep_rejeitado(BASE + MODAL_COM_ERRO)


def _fluxo(paginas: dict[str, str], depois_de_confirmar: str, sem_cep_depois=False):
    def ao_clicar(pagina: PaginaFalsa, seletor):
        if seletor in SELETORES.abrir_local:
            pagina.atual = pagina.atual + MODAL
        elif seletor in SELETORES.confirmar:
            pagina.atual = depois_de_confirmar
            if not sem_cep_depois:
                pagina.paginas["*"] = depois_de_confirmar

    pagina = PaginaFalsa(paginas, ao_clicar=ao_clicar)
    return pagina, NavegadorFalso(pagina)


def _provedor(navegador, config):
    return FreteAmazonNavegador(navegador, config, hoje=lambda: HOJE, intervalo=IntervaloImediato())


async def teste_fluxo_aplica_o_cep_uma_vez_e_cota_cada_produto(config):
    pagina, navegador = _fluxo({"*": BASE}, PAGO)
    destino = {}
    await _provedor(navegador, config).cotar(["B0CP6CVJSG", "B0CP6CJ8JG"], "01310-100", destino)
    assert {a: c.status for a, c in destino.items()} == {
        "B0CP6CVJSG": StatusCotacao.COTADO,
        "B0CP6CJ8JG": StatusCotacao.COTADO,
    }
    assert destino["B0CP6CJ8JG"].valor == 1990
    assert navegador.sessoes == 1
    assert pagina.abertas == [url_do_produto("B0CP6CVJSG"), url_do_produto("B0CP6CJ8JG")]
    assert sum(1 for s in pagina.cliques if s in SELETORES.abrir_local) == 1
    assert [v for _, v in pagina.preenchidos] == ["01310", "100"]


async def teste_seletor_de_local_usa_fallback_por_aria_label(config):
    sem_ids = BASE.replace('id="contextualIngressPtLink"', "").replace(
        'id="nav-global-location-popover-link"', ""
    )
    pagina, navegador = _fluxo({"*": sem_ids}, PAGO)
    destino = {}
    await _provedor(navegador, config).cotar(["B0CP6CVJSG"], "01310100", destino)
    assert destino["B0CP6CVJSG"].status is StatusCotacao.COTADO
    assert pagina.cliques[0].estrategia is Estrategia.ROTULO


async def teste_cep_rejeitado_encerra_a_cotacao(config):
    pagina, navegador = _fluxo({"*": BASE}, BASE + MODAL_COM_ERRO, sem_cep_depois=True)
    destino = {}
    await _provedor(navegador, config).cotar(["B0CP6CVJSG", "B0CP6CJ8JG"], "00000000", destino)
    assert destino["B0CP6CVJSG"].status is StatusCotacao.CEP_REJEITADO
    assert destino["B0CP6CJ8JG"].status is StatusCotacao.CEP_REJEITADO
    assert len(pagina.abertas) == 1


async def teste_challenge_para_tudo_sem_tentar_contornar(config):
    captcha = '<html><form action="/errors/validateCaptcha"></form></html>'
    pagina, navegador = _fluxo({"*": captcha}, PAGO)
    destino = {}
    await _provedor(navegador, config).cotar(["A1", "A2", "A3"], "01310100", destino)
    assert destino["A1"].status is StatusCotacao.DESAFIO
    assert destino["A2"].status is StatusCotacao.INTERROMPIDO
    assert destino["A3"].status is StatusCotacao.INTERROMPIDO
    assert pagina.abertas == [url_do_produto("A1")]
    assert not pagina.cliques and not pagina.preenchidos


async def teste_redirecionamento_para_login_encerra(config):
    pagina = PaginaFalsa(
        {"*": "<html></html>"}, url_final=lambda _: "https://www.amazon.com.br/ap/signin"
    )
    destino = {}
    await _provedor(NavegadorFalso(pagina), config).cotar(["A1"], "01310100", destino)
    assert destino["A1"].status is StatusCotacao.LOGIN


async def teste_sem_seletor_de_local_vira_status_e_nao_erro(config):
    pagina = PaginaFalsa({"*": "<html><body><div id='dp'>produto</div></body></html>"})
    destino = {}
    await _provedor(NavegadorFalso(pagina), config).cotar(["A1", "A2"], "01310100", destino)
    assert destino["A1"].status is StatusCotacao.SEM_SELETOR
    assert destino["A2"].status is StatusCotacao.SEM_SELETOR


def teste_seletores_tem_fallback_em_cada_passo():
    for nome in ("abrir_local", "cep_inteiro", "confirmar", "fechar_aviso"):
        estrategias = {s.estrategia for s in getattr(SELETORES, nome)}
        assert len(getattr(SELETORES, nome)) >= 2, nome
        assert estrategias - {Estrategia.CSS}, nome


@pytest.mark.skip(reason="browser execution unavailable in current environment")
async def teste_ao_vivo_frete_amazon_com_playwright(config):
    from app.navegador.playwright import NavegadorPlaywright

    navegador = NavegadorPlaywright(config)
    destino = {}
    try:
        await FreteAmazonNavegador(navegador, config).cotar(["B0CP6CVJSG"], "01310100", destino)
    finally:
        await navegador.fechar()
    assert destino["B0CP6CVJSG"].status in set(StatusCotacao)
