import importlib
import pkgutil

import pytest

import scripts


@pytest.mark.parametrize("nome", [m.name for m in pkgutil.iter_modules(scripts.__path__)])
def teste_scripts_importam_sem_erro(nome):
    modulo = importlib.import_module(f"scripts.{nome}")
    assert hasattr(modulo, "main")


def teste_marca_so_entra_quando_no_titulo_quase_sempre_e_ela():
    from scripts.gerar_marcas import marcas

    pares = [
        ("Smart TV Samsung 55", "Samsung"),
        ("Monitor Samsung 24", "Samsung"),
        ("Celular Samsung Galaxy", "SAMSUNG"),
        # "power" é marca de uma loja, mas aparece em produtos de muitas marcas
        ("Liquidificador Power Mondial", "Power"),
        ("Fonte Power Gamer", "Power"),
        ("Ventilador Power Arno", "Power"),
        ("Secador Power Philco", "Philco"),
        ("Secador Power Britania", "Britania"),
        ("Secador Power Arno", "Arno"),
        ("Secador Power Wap", "Wap"),
        ("Liquidificador Genérico", "Genérico"),
    ]
    assert marcas(pares, minimo=3, precisao=0.6) == ["samsung"]


def teste_frequencia_conta_titulos_na_forma_que_a_relevancia_compara():
    from scripts.gerar_frequencias import frequencias

    titulos = [
        "Camiseta Manga Curta Preta",
        "Blusa Manga Longa Manga Bufante",
        "Suco de Manga 900ml",
        "Boa Noite Punpun Vol. 1",
    ]
    total, contagem = frequencias(titulos, minimo=2)
    assert total == 4
    # conta títulos, não repetições; abaixo do mínimo fica de fora e conta como raro
    assert contagem == {"manga": 3}
    assert frequencias(["Air Fryer Mondial", "Fritadeira Airfryer Philco"], 1)[1]["airfryer"] == 2


def teste_tipo_e_a_palavra_que_quase_sempre_abre_o_titulo():
    from scripts.gerar_frequencias import tipos

    titulos = [
        "Camiseta Manga Curta Preta",
        "Camiseta Básica Manga Longa",
        "Kit 3 Camisetas Algodão",
        "Mangá One Piece Vol. 1",
        "Moto G85 5G 256GB",
        "Smartphone Moto G84",
        "Smartphone Moto G54",
    ]
    # "manga" abre 1 de 3 títulos e "moto" 1 de 3; "kit" é coletivo e cede a vez
    assert tipos(titulos, minimo=2, fracao=0.5) == ["camiseta", "celular"]
