import json
import math

import pytest

from scripts.avaliar_busca import CONSULTAS, carregar_consultas, casa, julgar, medir, normalizar


def teste_normalizar_separa_numero_de_unidade_e_tira_acento():
    assert normalizar("Panela de Pressão 4,5L 110V RTX4060") == (
        " panela de pressao 4 5 l 110 v rtx 4060 "
    )


@pytest.mark.parametrize(
    ("termo", "texto", "esperado"),
    [
        ("110v", "Geladeira 110V Inox", True),
        ("4 prateleiras", "Estante 4 Prateleiras", True),
        ("4 prateleiras", "Estante 14 Prateleiras", False),
        ("1 l", "Garrafa 1,8 L", False),
        ("air fry*", "Fritadeira Air Fryer", True),
        ("^capa", "Capa para iPhone", True),
        ("^capa", "iPhone com capa", False),
        ("re: \\d{4} w ", "Chuveiro 7500W", True),
    ],
)
def teste_termo_casa_palavras_inteiras(termo, texto, esperado):
    assert casa(normalizar(texto), termo) is esperado


CRITERIO = {
    "exige": [["geladeira", "refrigerador"]],
    "atributos": [
        {"nome": "voltagem", "aceita": ["110 v", "bivolt"], "rivais": ["220 v"]},
        {"nome": "modelo", "aceita": ["inox"], "rivais": [], "exclui": ["look"]},
    ],
    "proibe": ["^borracha"],
    "ean": "7899307521331",
}


@pytest.mark.parametrize(
    ("titulo", "ean", "relevante", "errada"),
    [
        ("Geladeira Inox 110V", None, True, False),
        ("Geladeira Inox Bivolt 127/220V", None, True, False),
        ("Geladeira Inox 220V", None, False, True),
        ("Geladeira Inox", None, False, False),
        ("Geladeira Inox Look 110V", None, False, True),
        ("Borracha de Geladeira Inox 110V", None, False, False),
        ("Estante Multy", "7899307521331", True, False),
    ],
)
def teste_julgamento_por_regra(titulo, ean, relevante, errada):
    assert julgar(CRITERIO, titulo, None, ean) == (relevante, errada)


def teste_marca_conta_no_julgamento():
    assert julgar({"exige": [["samsung"]]}, "Soundbar HW-B550", "Samsung", None) == (True, False)


def _oferta(id, loja="a", titulo="geladeira inox 110v"):
    return {"id": id, "loja": loja, "titulo": titulo, "marca": None, "ean": None}


def teste_metricas_com_recall_por_pooling():
    criterios = {"q": {"id": "q", "conjunto": "teste", **CRITERIO}}
    ruim = _oferta("x", titulo="geladeira inox 220v")
    execucoes = {
        "antes": [{"id": "q", "requisicoes": 4, "exibidas": [ruim, _oferta("r1")], "ocultas": []}],
        "depois": [
            {
                "id": "q",
                "requisicoes": 6,
                "exibidas": [_oferta("r1"), _oferta("r2", loja="b")],
                "ocultas": [ruim],
            }
        ],
    }
    resultado = medir(execucoes, criterios)
    antes, depois = resultado["antes"]["teste"], resultado["depois"]["teste"]
    assert antes["p@5"] == pytest.approx(0.2)
    assert antes["mrr"] == pytest.approx(0.5)
    assert antes["recall@10"] == pytest.approx(0.5)
    assert antes["variante_errada@10"] == pytest.approx(0.5)
    ideal = 1 + 1 / math.log2(3)
    assert antes["ndcg@10"] == pytest.approx((1 / math.log2(3)) / ideal, abs=1e-4)
    assert depois["p@10"] == pytest.approx(0.2)
    assert depois["mrr"] == depois["ndcg@10"] == depois["recall@20"] == 1
    assert depois["lojas_com_relevante"] == 2
    assert depois["requisicoes"] == 6
    assert depois["zero_resultados"] == 0


def teste_consultas_de_avaliacao_sao_validas():
    consultas = carregar_consultas(CONSULTAS)
    assert len(consultas) >= 60
    assert len({c["id"] for c in consultas}) == len(consultas)
    conjuntos = [c["conjunto"] for c in consultas]
    assert 35 <= conjuntos.count("desenvolvimento") <= 45
    assert 18 <= conjuntos.count("teste") <= 25
    assert len({c["categoria"] for c in consultas}) >= 10
    for c in consultas:
        assert c["exige"] or c.get("atributos")
        assert all(not t.startswith("$") for a in c.get("atributos", []) for t in a["rivais"])
    json.dumps(consultas)
