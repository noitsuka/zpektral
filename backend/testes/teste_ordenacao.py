import pytest

from app.modelos import Frete, Loja, Oferta, Origem, Pagamento, Parcelamento, StatusFrete
from app.ordenacao import FiltroFrete, Filtros, Ordem, Pesos, aplicar, notas_custo_beneficio


def oferta(
    id: str,
    preco: int,
    *,
    frete: Frete | None = None,
    pix: int | None = None,
    rel: int = 100,
    loja: str = "a",
    original: int | None = None,
    origem: Origem = Origem.LOJA,
    disponivel: bool = True,
    ean: str | None = None,
    titulo: str | None = None,
    parcelas: Parcelamento | None = None,
) -> Oferta:
    return Oferta(
        id=id,
        titulo=titulo or id,
        link="",
        loja=Loja(loja, loja.upper()),
        preco=preco,
        preco_pix=pix,
        preco_original=original,
        frete=frete or Frete(StatusFrete.NAO_INFORMADO),
        relevancia=rel,
        origem=origem,
        disponivel=disponivel,
        ean=ean,
        parcelamento=parcelas,
    ).consolidar()


def cotada(valor: int, dias: float = 5) -> Frete:
    return Frete(StatusFrete.CALCULADO, valor=valor, prazo=f"até {dias} dias", prazo_dias=dias)


def ids(ofertas):
    return [o.id for o in ofertas]


def teste_total_usa_pix_quando_mais_barato_e_soma_frete():
    o = oferta("x", 10000, pix=9500, frete=cotada(1500))
    assert o.melhor_preco == 9500
    assert o.total == 11000
    assert o.total_exato


def teste_pix_acima_do_cartao_e_ignorado():
    assert oferta("x", 10000, pix=12000).melhor_preco == 10000


def teste_preco_de_tabela_abaixo_do_preco_e_descartado():
    assert oferta("x", 10000, original=9000).preco_original is None


def teste_menor_total_conta_o_frete():
    barato_longe = oferta("cheap", 10000, frete=cotada(5000))
    caro_gratis = oferta("pricier", 12000, frete=cotada(0))
    resultado, _ = aplicar([barato_longe, caro_gratis], Filtros(ordem=Ordem.MENOR_TOTAL))
    assert ids(resultado) == ["pricier", "cheap"]


def teste_menor_total_poe_o_mais_barato_na_frente_mesmo_sem_frete():
    sem_frete = oferta("no_shipping", 9000)
    anunciado = oferta("advertised", 9500, frete=Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0))
    exatas = oferta("exact", 9000, frete=cotada(1000))
    resultado, _ = aplicar([exatas, anunciado, sem_frete], Filtros(ordem=Ordem.MENOR_TOTAL))
    assert ids(resultado) == ["no_shipping", "advertised", "exact"]


def teste_menor_total_empatado_prefere_o_total_conferido():
    sem_frete = oferta("no_shipping", 10000)
    exatas = oferta("exact", 9000, frete=cotada(1000))
    resultado, _ = aplicar([sem_frete, exatas], Filtros(ordem=Ordem.MENOR_TOTAL))
    assert ids(resultado) == ["exact", "no_shipping"]


def teste_relevancia_empatada_vai_pelo_preco_e_nao_pelo_frete_cotado():
    caro_cotado = oferta("quoted", 15000, frete=cotada(0))
    barato_sem_frete = oferta("cheap", 9000)
    resultado, _ = aplicar([caro_cotado, barato_sem_frete], Filtros())
    assert ids(resultado) == ["cheap", "quoted"]


def teste_sem_cep_menor_total_e_por_preco():
    conjunto = [oferta("b", 200), oferta("a", 100)]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.MENOR_TOTAL))[0]) == ["a", "b"]


def teste_relevancia_e_depois_total():
    conjunto = [oferta("b", 300, rel=90), oferta("a", 200, rel=100), oferta("c", 100, rel=100)]
    resultado, _ = aplicar(conjunto, Filtros())
    assert ids(resultado) == ["c", "a", "b"]


def teste_piso_de_relevancia():
    conjunto = [oferta("keep", 1, rel=70), oferta("drop", 1, rel=69)]
    assert ids(aplicar(conjunto, Filtros())[0]) == ["keep"]
    assert len(aplicar(conjunto, Filtros(relevancia_min=0))[0]) == 2


def teste_faixa_de_preco_inclusiva_e_sobre_o_total():
    conjunto = [oferta("a", 1000, frete=cotada(500)), oferta("b", 2000), oferta("c", 3000)]
    resultado, _ = aplicar(
        conjunto, Filtros(preco_min=1500, preco_max=2000, ordem=Ordem.MENOR_TOTAL)
    )
    assert ids(resultado) == ["a", "b"]


def teste_filtros_de_loja_e_origem():
    conjunto = [
        oferta("a", 1, loja="x"),
        oferta("b", 1, loja="y", origem=Origem.COMPARADOR),
        oferta("c", 1, loja="z", origem=Origem.MARKETPLACE),
    ]
    assert ids(aplicar(conjunto, Filtros(lojas=frozenset({"x", "z"})))[0]) == ["a", "c"]
    assert ids(
        aplicar(conjunto, Filtros(origens=frozenset({Origem.LOJA, Origem.MARKETPLACE})))[0]
    ) == [
        "a",
        "c",
    ]


def teste_filtros_de_frete():
    conjunto = [
        oferta("quoted_free", 100, frete=cotada(0)),
        oferta("quoted_paid", 100, frete=cotada(10)),
        oferta("advertised", 100, frete=Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0)),
        oferta("unknown", 100),
    ]
    gratis = aplicar(conjunto, Filtros(frete=FiltroFrete.GRATIS))[0]
    assert set(ids(gratis)) == {"quoted_free", "advertised"}
    exatas = aplicar(conjunto, Filtros(frete=FiltroFrete.CALCULADO))[0]
    assert set(ids(exatas)) == {"quoted_free", "quoted_paid"}


def teste_indisponiveis_e_sem_entrega_ficam_ocultos_por_padrao():
    conjunto = [
        oferta("ok", 1),
        oferta("sold_out", 1, disponivel=False),
        oferta("far", 1, frete=Frete(StatusFrete.NAO_ENTREGA)),
    ]
    assert ids(aplicar(conjunto, Filtros())[0]) == ["ok"]
    assert len(aplicar(conjunto, Filtros(apenas_disponiveis=False))[0]) == 3


def teste_mais_rapida_poe_prazo_desconhecido_no_fim():
    conjunto = [
        oferta("slow", 1, frete=cotada(0, 10)),
        oferta("none", 1),
        oferta("fast", 9, frete=cotada(0, 1)),
    ]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.ENTREGA_RAPIDA))[0]) == [
        "fast",
        "slow",
        "none",
    ]


def teste_ordens_por_preco_e_desconto():
    conjunto = [
        oferta("mid", 200, original=400),
        oferta("low", 100),
        oferta("high", 300, original=310),
    ]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.MENOR_PRECO))[0]) == ["low", "mid", "high"]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.MAIOR_PRECO))[0]) == ["high", "mid", "low"]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.MAIOR_DESCONTO))[0])[0] == "mid"


def teste_facetas_ignoram_o_proprio_filtro_do_usuario():
    conjunto = [oferta("a", 100, loja="x"), oferta("b", 900, loja="y"), oferta("c", 500, loja="y")]
    resultado, facetas = aplicar(conjunto, Filtros(lojas=frozenset({"x"})))
    assert ids(resultado) == ["a"]
    assert [(s.id, s.quantidade) for s in facetas.lojas] == [("y", 2), ("x", 1)]
    assert (facetas.preco_min, facetas.preco_max) == (100, 900)


def teste_conjunto_vazio_tem_facetas_vazias():
    resultado, facetas = aplicar([], Filtros())
    assert resultado == [] and facetas.lojas == [] and facetas.preco_min is None


def teste_pagamento_muda_total_e_ordem():
    loja_pix = oferta("pix", 100000, pix=85000, frete=cotada(2000))
    loja_cartao = oferta(
        "card", 90000, frete=cotada(0), parcelas=Parcelamento(12, 7500, 90000, False)
    )

    def por(pagamento):
        f = Filtros(ordem=Ordem.MENOR_TOTAL, pagamento=pagamento)
        return ids(aplicar([loja_pix, loja_cartao], f)[0])

    assert por(Pagamento.PIX) == ["pix", "card"]
    assert por(Pagamento.PARCELADO) == ["card", "pix"]
    assert por(Pagamento.AVISTA) == ["card", "pix"]
    assert loja_pix.totais.pix == 87000 and loja_pix.totais.avista == 102000
    assert loja_cartao.totais.parcelado == 90000


def teste_parcelado_com_juros_custa_mais():
    o = oferta("x", 100000, parcelas=Parcelamento(12, 9500, 114000, True), frete=cotada(1000))
    assert o.total_para(Pagamento.PARCELADO) == 115000
    assert o.total_para(Pagamento.AVISTA) == 101000


def teste_faixa_de_preco_segue_o_pagamento():
    o = oferta("x", 10000, pix=9000)
    assert ids(aplicar([o], Filtros(preco_max=9500, pagamento=Pagamento.PIX))[0]) == ["x"]
    assert ids(aplicar([o], Filtros(preco_max=9500, pagamento=Pagamento.AVISTA))[0]) == []


def teste_filtro_de_voltagem_tira_so_a_errada():
    conjunto = [
        oferta("v110", 1, titulo="Geladeira Frost Free 110V"),
        oferta("v220", 1, titulo="Geladeira Frost Free 220V"),
        oferta("bivolt", 1, titulo="Geladeira Frost Free Bivolt"),
        oferta("unknown", 1, titulo="Geladeira Frost Free"),
    ]
    solta = aplicar(conjunto, Filtros(voltagens=frozenset({"220V"})))[0]
    assert set(ids(solta)) == {"v220", "bivolt", "unknown"}
    estrita = aplicar(conjunto, Filtros(voltagens=frozenset({"220V"}), voltagem_estrita=True))[0]
    assert set(ids(estrita)) == {"v220", "bivolt"}
    _, facetas = aplicar(conjunto, Filtros())
    assert facetas.voltagens == {"110V": 1, "220V": 1, "bivolt": 1}


def teste_custo_beneficio_troca_preco_por_rapidez_e_certeza():
    barato_lento_incerto = oferta("cheap", 100000)
    justo_rapido_cotado = oferta("fair", 103000, frete=cotada(0, 1))
    conjunto = [barato_lento_incerto, justo_rapido_cotado]
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.CUSTO_BENEFICIO))[0]) == ["fair", "cheap"]
    so_preco = Pesos(preco=1, prazo=0, relevancia=0, confianca=0)
    assert ids(aplicar(conjunto, Filtros(ordem=Ordem.CUSTO_BENEFICIO, pesos=so_preco))[0]) == [
        "cheap",
        "fair",
    ]


def teste_notas_de_custo_beneficio_limitadas():
    conjunto = [oferta(str(i), 1000 * (i + 1), frete=cotada(0, i)) for i in range(10)]
    notas = notas_custo_beneficio(conjunto, Pagamento.MELHOR, Pesos())
    assert all(0 <= s <= 1 for s in notas.values())
    assert notas["0"] == max(notas.values())
    assert notas_custo_beneficio([], Pagamento.MELHOR, Pesos()) == {}


@pytest.mark.parametrize(
    ("titulo", "esperada"),
    [
        ("iPhone 13 128GB Usado", "usado"),
        ("Notebook Dell Seminovo i5", "usado"),
        ("Placa de Vídeo RX 5600 XT (usado)", "usado"),
        ("Smartphone Galaxy S22 Recondicionado", "recondicionado"),
        ("Geladeira Brastemp de Vitrine", "recondicionado"),
        ("Air Fryer Mondial Open Box", "recondicionado"),
        ("MacBook Air Recertificado Apple", "recondicionado"),
        ("Óleo de coco que pode ser usado na air fryer", "novo"),
        ("Papel manteiga usado em air fryer 50 unidades", "novo"),
        ("Tênis Outlet Nike Revolution 6", "novo"),
        ("Smart TV LG 55 4K", "novo"),
    ],
)
def teste_condicao_do_titulo_evita_falsos_usados(titulo, esperada):
    from app.modelos import condicao_do_titulo

    assert condicao_do_titulo(titulo) == esperada


def teste_contagens_seguem_o_filtro_de_condicao_e_a_condicao_conta_tudo():
    conjunto = [
        oferta("novo", 1000, loja="x", titulo="iPhone 13 128GB"),
        oferta("usado1", 800, loja="y", titulo="Usado: iPhone 13 128GB Bom"),
        oferta("usado2", 700, loja="y", titulo="Usado: iPhone 13 128GB Excelente"),
    ]
    resultado, facetas = aplicar(conjunto, Filtros(relevancia_min=0))
    assert ids(resultado) == ["novo"]
    assert [(s.id, s.quantidade) for s in facetas.lojas] == [("x", 1)]
    assert (facetas.preco_min, facetas.preco_max) == (1000, 1000)
    assert facetas.condicoes == {"usado": 2, "novo": 1}
