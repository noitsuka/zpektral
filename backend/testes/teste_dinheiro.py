import pytest

from app.dinheiro import ler_reais, para_centavos


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (0, 0),
        (1, 100),
        (0.1, 10),
        (0.1 + 0.2, 30),
        (2999.9, 299990),
        (8999.1, 899910),
        (7559.1, 755910),
        (3091.75, 309175),
        (1545.875, 154588),
        (0.005, 1),
        (0.004, 0),
        ("1299.90", 129990),
        (19.99, 1999),
        (1e-9, 0),
    ],
)
def teste_para_centavos_e_exato(valor, esperado):
    assert para_centavos(valor) == esperado


def teste_para_centavos_nunca_desvia_com_float():
    for reais in range(0, 100_000, 7):
        for centavos in (0, 1, 9, 10, 33, 50, 99):
            valor = float(f"{reais}.{centavos:02d}")
            assert para_centavos(valor) == reais * 100 + centavos


def teste_para_centavos_rejeita_lixo():
    with pytest.raises(ValueError):
        para_centavos("abc")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("R$ 839,90", 83990),
        ("R$ 1.299,90", 129990),
        ("R$\xa01.299,90", 129990),
        ("10x de R$ 1513,78", 1000),
        ("1299,9", 129990),
        ("12.345.678,01", 1234567801),
        ("R$ 5", 500),
    ],
)
def teste_ler_reais(texto, esperado):
    assert ler_reais(texto) == esperado


def teste_ler_reais_rejeita_texto_sem_valor():
    with pytest.raises(ValueError):
        ler_reais("grátis")


@pytest.mark.parametrize(
    ("esperado", "texto"),
    [(0, "R$ 0,00"), (5, "R$ 0,05"), (129990, "R$ 1.299,90"), (1234567, "R$ 12.345,67")],
)
def teste_ler_reais_com_milhar_e_centavos(esperado, texto):
    assert ler_reais(texto) == esperado
