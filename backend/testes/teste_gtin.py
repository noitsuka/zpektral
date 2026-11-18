from app.fontes.base import ContextoBusca
from app.relevancia import interpretar_consulta, texto_para_lojas


def _ctx(consulta: str) -> ContextoBusca:
    return ContextoBusca(texto_para_lojas(consulta), interpretar_consulta(consulta), None)


def teste_ean_valido_na_consulta_vira_identificador():
    assert interpretar_consulta("estante 7899307521331").gtin == "7899307521331"
    assert interpretar_consulta("7899307521331").gtin == "7899307521331"


def teste_numero_que_nao_e_ean_e_ignorado():
    assert interpretar_consulta("7899307521332").gtin is None
    assert interpretar_consulta("rtx 4060").gtin is None
    assert interpretar_consulta("cabo 12345670").gtin is None


def teste_lojas_recebem_so_o_ean():
    assert texto_para_lojas("estante 7899307521331") == "7899307521331"


def teste_oferta_com_o_mesmo_ean_e_o_produto_certo():
    ctx = _ctx("7899307521331")
    titulo = "Estante Para Livros Com 4 Prateleiras Multy Menta Artely"
    assert ctx.relevancia_de(titulo, ean="7899307521331") == 100
    assert ctx.relevancia_de(titulo, ean="07899307521331") == 100
    assert ctx.relevancia_de(titulo, ean="7909903385180") <= 40
    assert ctx.relevancia_de(titulo) <= 40


def teste_oferta_com_o_mesmo_ean_nao_tem_termo_ausente():
    from app.relevancia import termos_ausentes

    consulta = interpretar_consulta("7899307521331")
    assert termos_ausentes(consulta, "Estante Multy", "7899307521331") == []
    assert termos_ausentes(consulta, "Estante Multy") == ["7899307521331"]
