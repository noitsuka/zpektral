import pytest

from app.agrupamento import (
    atribuir_grupos,
    chave_propria,
    especificacoes,
    marcar_fora_da_curva,
)
from app.modelos import Alerta, Loja, Oferta


def oferta(id: str, titulo: str, preco: int = 1000, loja: str | None = None, ean=None) -> Oferta:
    id_loja = loja or id
    return Oferta(
        id=id, titulo=titulo, link="x", loja=Loja(id_loja, id_loja), preco=preco, ean=ean
    ).consolidar()


def grupos_de(ofertas):
    atribuir_grupos(ofertas)
    por: dict[str | None, set[str]] = {}
    for o in ofertas:
        por.setdefault(o.grupo, set()).add(o.id)
    return por


@pytest.mark.parametrize(
    ("titulo", "modelos"),
    [
        ('Smart TV LG 55" 55QNED70BSA 4K', {"55qned70bsa"}),
        ("Smart TV Samsung 55 Polegadas UN55U8000FGXZD Crystal", {"un55u8000fgxzd"}),
        ("Notebook Acer Nitro V15 - ANV15-52-96AQ", {"anv155296aq"}),
        ("Placa de Vídeo RTX 4060 8GB GDDR6", set()),
        ("iPhone 15 128GB Preto", set()),
        ("Processador Ryzen 5 5600 AM4", set()),
        ("SSD NVMe 1TB PCIe 4.0", set()),
    ],
)
def teste_codigos_de_modelo_ignoram_medidas_e_familias(titulo, modelos):
    assert set(especificacoes(oferta("x", titulo)).modelos) == modelos


def teste_mesmo_ean_agrupa_entre_lojas():
    g = grupos_de(
        [
            oferta("a", "Geladeira Brastemp", ean="789"),
            oferta("b", "Refrigerador Brastemp Frost Free", ean="789"),
            oferta("c", "Outra coisa", ean="111"),
        ]
    )
    assert {"a", "b"} in g.values()
    assert g["g:111"] == {"c"}


def teste_mesmo_codigo_de_modelo_agrupa_titulos_diferentes():
    g = grupos_de(
        [
            oferta("kabum", 'Smart TV LG 55" QNED 55QNED70BSA 4K WebOS'),
            oferta("carrefour", "Smart TV LG 55 Polegadas 55QNED70BSA 4K UHD QNED Mini LED"),
            oferta("web", "TV LG 55QNED70BSA"),
        ]
    )
    assert g == {"g:55qned70bsa": {"kabum", "carrefour", "web"}}


def teste_especificacoes_em_conflito_nunca_se_unem():
    g = grupos_de(
        [
            oferta("a", "Smartphone Galaxy SM-S921B 128GB Preto"),
            oferta("b", "Smartphone Galaxy SM-S921B 256GB Preto"),
            oferta("c", "Geladeira Brastemp BRM44HK 110V"),
            oferta("d", "Geladeira Brastemp BRM44HK 220V"),
            oferta("e", "Geladeira Brastemp BRM44HK Bivolt"),
        ]
    )
    conjuntos = [s for s in g.values() if len(s) > 1]
    assert {"a", "b"} not in conjuntos
    assert not any({"c", "d"} <= s for s in conjuntos)


def teste_titulo_sem_especificacao_nao_une_duas_variantes():
    g = grupos_de(
        [
            oferta("a", "Smartphone Galaxy SM-S921B 128GB"),
            oferta("b", "Smartphone Galaxy SM-S921B 256GB"),
            oferta("c", "Smartphone Galaxy SM-S921B"),
        ]
    )
    assert all(len(membros) == 1 for membros in g.values())


def teste_ean_e_modelo_formam_um_grupo_com_id_estavel():
    ofertas = [
        oferta("a", "Smart TV LG 55QNED70BSA", ean="7893299"),
        oferta("b", "TV LG 55QNED70BSA 55 polegadas"),
    ]
    atribuir_grupos(ofertas)
    assert ofertas[0].grupo == ofertas[1].grupo
    de_novo = [ofertas[1], ofertas[0]]
    atribuir_grupos(de_novo)
    assert de_novo[0].grupo == ofertas[0].grupo


def teste_peca_nunca_entra_no_grupo_do_aparelho():
    g = grupos_de(
        [
            oferta("fryer", "Fritadeira Air Fryer Mondial AF-55i 5,5L"),
            oferta("fryer2", "Air Fryer Mondial Family AF-55i"),
            oferta("part", "Cuba Metalica Antiaderente da Air Fryer Mondial AF-55i"),
        ]
    )
    assert {"fryer", "fryer2"} in g.values()
    assert not any("part" in membros and len(membros) > 1 for membros in g.values())


def teste_ofertas_sem_identidade_ficam_sem_grupo():
    ofertas = [oferta("a", "Panela de pressão 4,5 litros"), oferta("b", "Panela de pressão 4,5L")]
    atribuir_grupos(ofertas)
    assert ofertas[0].grupo is None and ofertas[1].grupo is None


def teste_chave_propria_prefere_ean():
    assert chave_propria(oferta("a", "TV 55QNED70BSA", ean="789")) == "g:789"
    assert chave_propria(oferta("a", "TV 55QNED70BSA")) == "g:55qned70bsa"
    assert chave_propria(oferta("a", "TV")) is None


def teste_fora_da_curva_so_com_lojas_suficientes():
    ofertas = [
        oferta("a", "TV X", 300000, "a", "1"),
        oferta("b", "TV X", 310000, "b", "1"),
        oferta("c", "TV X", 320000, "c", "1"),
        oferta("d", "TV X", 50000, "d", "1"),
    ]
    atribuir_grupos(ofertas)
    marcar_fora_da_curva(ofertas)
    assert ofertas[3].alertas == [Alerta.PRECO_FORA_DA_CURVA]
    assert all(not o.alertas for o in ofertas[:3])

    par = [oferta("a", "TV Y", 300000, "a", "2"), oferta("b", "TV Y", 10, "b", "2")]
    atribuir_grupos(par)
    marcar_fora_da_curva(par)
    assert not par[1].alertas


def teste_muito_abaixo_do_nivel_de_preco_e_rebaixado_e_alertado():
    from app.agrupamento import rebaixar_muito_abaixo

    geladeiras = [oferta(f"g{i}", "Geladeira Frost Free", 300000 + i * 1000) for i in range(12)]
    for o in geladeiras:
        o.relevancia = 100
    lampada = oferta("lamp", "Lâmpada Tubular Geladeira", 3000)
    lampada.relevancia = 100
    geladeira_barata = oferta("cheap", "Geladeira Usada", 90000)
    geladeira_barata.relevancia = 100
    rebaixar_muito_abaixo([*geladeiras, lampada, geladeira_barata])
    assert lampada.relevancia == 50 and "preco_fora_da_curva" in lampada.alertas
    assert geladeira_barata.relevancia == 100


def teste_conjuntos_pequenos_ou_misturados_ficam_como_estao():
    from app.agrupamento import rebaixar_muito_abaixo

    poucas = [oferta(f"g{i}", "Geladeira", 300000) for i in range(5)] + [oferta("l", "Lâmpada", 1)]
    for o in poucas:
        o.relevancia = 100
    rebaixar_muito_abaixo(poucas)
    assert poucas[-1].relevancia == 100


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("7891234567895", "7891234567895"),
        ("07891234567895", "7891234567895"),
        (" 7891234567895 ", "7891234567895"),
        ("40141215802", "0040141215802"),
        ("40141215803", None),
        ("012345678905", "0012345678905"),
        ("12345678905", "0012345678905"),
        ("96385074", "0000096385074"),
        ("7891234567890", None),
        ("0000000000000", None),
        ("1111111111111", None),
        ("SEM GTIN", None),
        ("1", None),
        ("123456789012345", None),
        (None, None),
        (7891234567895, "7891234567895"),
    ],
)
def teste_ean_so_vale_com_digito_verificador_e_forma_unica(bruto, esperado):
    from app.agrupamento import normalizar_ean

    assert normalizar_ean(bruto) == esperado


def teste_ean_falso_nao_junta_produtos_diferentes():
    from app.agrupamento import normalizar_ean

    ofertas = [
        oferta("a", "Geladeira Brastemp", ean="0000000000000"),
        oferta("b", "Fralda Pampers G", ean="0000000000000"),
    ]
    for o in ofertas:
        o.ean = normalizar_ean(o.ean)
    atribuir_grupos(ofertas)
    assert ofertas[0].grupo is None and ofertas[1].grupo is None


def teste_acessorio_e_comida_na_busca_do_aparelho_caem():
    from app.agrupamento import rebaixar_muito_abaixo

    fritadeiras = [oferta(f"f{i}", "Air Fryer 4L", 25000 + i * 1500) for i in range(12)]
    pizza = oferta("pizza", "Pizza Calabresa Air Fryer", 1376)
    cesto = oferta("cesto", "Cesto de Papel Air Fryer", 5500)
    barata = oferta("barata", "Air Fryer 3L", 14990)
    for o in [*fritadeiras, pizza, cesto, barata]:
        o.relevancia = 100
    rebaixar_muito_abaixo([*fritadeiras, pizza, cesto, barata])
    assert pizza.relevancia == 50 and cesto.relevancia == 50
    assert barata.relevancia == 100
