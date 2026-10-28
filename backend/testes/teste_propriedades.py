from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.agrupamento import normalizar_ean
from app.busca import PRECO_MAXIMO_CENTAVOS, chave_cache, sanear
from app.dinheiro import ler_reais
from app.importacao import estimar_importacao
from app.modelos import Frete, Loja, Oferta, Pagamento, StatusFrete
from app.ordenacao import Filtros, Ordem, aplicar, certeza

centavos = st.integers(min_value=0, max_value=10**10)


@given(centavos)
def teste_ler_reais_entende_qualquer_valor_formatado(valor):
    inteiro, centavos = divmod(valor, 100)
    texto = f"R$ {inteiro:,}".replace(",", ".") + f",{centavos:02d}"
    assert ler_reais(texto) == valor


@given(st.text(alphabet="0123456789 ", min_size=0, max_size=16))
def teste_ean_normalizado_tem_digito_valido_e_nao_muda_de_novo(bruto):
    ean = normalizar_ean(bruto)
    if ean is None:
        return
    assert ean.isdigit() and len(ean) in (13, 14)
    gtin = ean.zfill(14)
    soma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(gtin[:-1])))
    assert (10 - soma % 10) % 10 == int(gtin[-1])
    assert normalizar_ean(ean) == ean


@given(
    produto=st.integers(min_value=1, max_value=10**8),
    frete=st.one_of(st.none(), st.integers(min_value=0, max_value=10**6)),
    cotacao=st.floats(min_value=1, max_value=20, allow_nan=False),
    importacao=st.floats(min_value=0, max_value=1, allow_nan=False),
    icms=st.floats(min_value=0, max_value=0.35, allow_nan=False),
)
def teste_icms_por_dentro_fecha_a_conta(produto, frete, cotacao, importacao, icms):
    preco, frete_brl, estimativa = estimar_importacao(produto, frete, cotacao, importacao, icms)
    assert preco >= 0 and (frete_brl or 0) >= 0
    assert estimativa.imposto_importacao >= 0 and estimativa.icms >= 0
    total = preco + (frete_brl or 0) + estimativa.impostos
    base = (Decimal(preco + (frete_brl or 0)) + estimativa.imposto_importacao) / (
        1 - Decimal(str(icms))
    )
    assert abs(Decimal(total) - base) <= 2


@given(st.text(min_size=1, max_size=40))
def teste_chave_de_cache_ignora_caixa_e_espacos(texto):
    variacao = "  " + texto.upper().replace(" ", "   ") + " "
    assert chave_cache(texto, None) == chave_cache(variacao, None)


def _ofertas():
    oferta = st.builds(
        lambda i, preco, frete, status, relevancia, loja, link: Oferta(
            id=f"l{loja}:{i}",
            titulo=f"Produto {i}",
            link=link,
            loja=Loja(f"l{loja}", f"Loja {loja}"),
            preco=preco,
            frete=Frete(status, valor=frete if status is StatusFrete.CALCULADO else None),
            relevancia=relevancia,
        ).consolidar(),
        i=st.integers(min_value=0, max_value=10**6),
        preco=st.integers(min_value=-5, max_value=PRECO_MAXIMO_CENTAVOS + 5),
        frete=st.integers(min_value=0, max_value=50_000),
        status=st.sampled_from(list(StatusFrete)),
        relevancia=st.integers(min_value=0, max_value=100),
        loja=st.integers(min_value=0, max_value=4),
        link=st.sampled_from(["https://loja.com.br/p", "http://loja.com.br/p", "javascript:x", ""]),
    )
    return st.lists(oferta, max_size=40)


@settings(max_examples=200)
@given(_ofertas())
def teste_saneamento_so_deixa_link_https_e_preco_possivel(ofertas):
    for o in sanear(ofertas):
        assert o.link.startswith("https://")
        assert 0 < o.preco <= PRECO_MAXIMO_CENTAVOS


@settings(max_examples=200)
@given(
    _ofertas(),
    st.sampled_from(list(Ordem)),
    st.sampled_from(list(Pagamento)),
    st.one_of(st.none(), st.integers(min_value=0, max_value=10**6)),
    st.one_of(st.none(), st.integers(min_value=0, max_value=10**8)),
)
def teste_filtros_e_ordem_nunca_inventam_ofertas(ofertas, ordem, pagamento, minimo, maximo):
    validas = sanear(ofertas)
    f = Filtros(
        ordem=ordem,
        pagamento=pagamento,
        relevancia_min=0,
        preco_min=minimo,
        preco_max=maximo,
        apenas_disponiveis=False,
    )
    resultado, facetas = aplicar(validas, f)
    ids = [o.id for o in resultado]
    assert len(ids) == len(set(ids))
    assert set(ids) <= {o.id for o in validas}
    for o in resultado:
        total = o.total_para(pagamento)
        assert minimo is None or total >= minimo
        assert maximo is None or total <= maximo
    if ordem is Ordem.MENOR_TOTAL:
        chaves = [(o.total_para(pagamento), certeza(o)) for o in resultado]
        assert chaves == sorted(chaves)
    assert sum(loja.quantidade for loja in facetas.lojas) >= len(resultado)
