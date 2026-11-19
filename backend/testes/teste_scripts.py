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
