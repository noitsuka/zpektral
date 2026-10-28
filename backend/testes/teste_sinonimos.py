import pytest

from app.busca import chave_cache
from app.relevancia import interpretar_consulta, pontuar, termos_do_texto, texto_para_lojas


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("maquina de lavar louça", "lava-louças"),
        ("lavadora de louças", "Lava Louças"),
        ("lavalouças", "lava louça"),
        ("refrigerador frost free", "geladeira frost free"),
        ("forno micro-ondas 30 litros", "microondas 30l"),
        ("smartphone samsung", "celular samsung"),
        ("televisão 55", "smart tv 55"),
        ("ar-condicionado 12000 btus", "ar condicionado 12000 btus"),
        ("fritadeira sem óleo", "air fryer"),
        ("headphone bluetooth", "fone de ouvido bluetooth"),
        ("video game", "console"),
    ],
)
def teste_formas_diferentes_do_mesmo_produto_viram_a_mesma_consulta(a, b):
    assert interpretar_consulta(a).termos == interpretar_consulta(b).termos


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("maquina de lavar louça", "Lava-Louças Brastemp 8 Serviços Inox"),
        ("lava-louças", "Máquina de Lavar Louças Electrolux 14 Serviços"),
        ("geladeira duplex", "Refrigerador Duplex Frost Free 450L"),
        ("microondas", "Forno Micro-ondas Panasonic 32L"),
        ("celular motorola", "Smartphone Motorola Moto G85 256GB"),
    ],
)
def teste_titulo_com_outro_nome_do_produto_casa_por_inteiro(consulta, titulo):
    assert pontuar(interpretar_consulta(consulta), titulo) >= 95


def teste_frase_mais_longa_vence():
    assert termos_do_texto("lavadora de louças") != termos_do_texto("lavadora de roupas")
    assert termos_do_texto("lavadora de alta pressão") != termos_do_texto("lavadora")
    assert termos_do_texto("maquina de lavar roupas") == termos_do_texto("lavadora")


def teste_peca_do_produto_continua_rebaixada():
    consulta = interpretar_consulta("maquina de lavar louça")
    assert pontuar(consulta, "Cesto Inferior para Lava-Louças Brastemp") < 40


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("maquina de lavar louça", "lava-louças"),
        ("Máquina de lavar louças Brastemp 8 serviços", "lava-louças Brastemp 8 serviços"),
        ("refrigerador Electrolux IF56", "geladeira Electrolux IF56"),
        ("forno de micro-ondas", "micro-ondas"),
        ("iPhone 15 Pro", "iPhone 15 Pro"),
        ("Galaxy SM-A556E", "Galaxy SM-A556E"),
    ],
)
def teste_lojas_recebem_o_nome_mais_comum(consulta, esperado):
    assert texto_para_lojas(consulta) == esperado


def teste_sinonimos_compartilham_a_mesma_busca():
    assert chave_cache("maquina de lavar louça", None) == chave_cache("Lava-Louças", None)
    assert chave_cache("iphone 15", None) != chave_cache("iphone 16", None)


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("fogao 4 bocas", "fogão 4 bocas"),
        ("geladiera frost free", "geladeira frost free"),
        ("maqina de lavar louca", "lava-louças"),
        ("ventlador de coluna", "ventilador de coluna"),
        ("liquidificadro", "liquidificador"),
        ("colchao casal", "colchão casal"),
        ("Consul CRM40", "Consul CRM40"),
        ("iphone 15", "iphone 15"),
        ("tv", "tv"),
    ],
)
def teste_pequenos_erros_e_acentos_sao_corrigidos_para_as_lojas(consulta, esperado):
    assert texto_para_lojas(consulta) == esperado


def teste_consulta_com_erro_casa_com_o_titulo_certo():
    consulta = interpretar_consulta("geladiera frost free")
    assert pontuar(consulta, "Geladeira Consul Frost Free 340L") >= 95


def teste_erros_compartilham_a_mesma_busca():
    assert chave_cache("fogao 4 bocas", None) == chave_cache("Fogão 4 bocas", None)
    assert chave_cache("geladiera", None) == chave_cache("geladeira", None)
