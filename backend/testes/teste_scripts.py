import importlib
import pkgutil

import pytest

import scripts


@pytest.mark.parametrize("nome", [m.name for m in pkgutil.iter_modules(scripts.__path__)])
def teste_scripts_importam_sem_erro(nome):
    modulo = importlib.import_module(f"scripts.{nome}")
    assert hasattr(modulo, "main") or hasattr(modulo, "principal")
