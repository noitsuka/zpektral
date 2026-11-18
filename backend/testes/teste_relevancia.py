import pytest

from app.relevancia import interpretar_consulta, normalizar, pontuar


def s(consulta: str, titulo: str) -> int:
    return pontuar(interpretar_consulta(consulta), titulo)


def teste_normalizar_remove_acentos_caixa_e_pontuacao():
    assert (
        normalizar("Geladeira Frost-Free  Inox 2ª Geração!")
        == "geladeira frost free inox 2a geracao"
    )


def teste_consulta_tira_palavras_vazias_e_separa_codigos():
    q = interpretar_consulta("Placa de vídeo RTX4060")
    assert q.termos == ("placa", "video", "rtx", "4060")
    assert q.pesos == (1.0, 1.0, 1.0, 2.0)


@pytest.mark.parametrize(
    "titulo",
    [
        'Smart TV Samsung 55" Crystal UHD 4K',
        "Smart Tv Hq Qled 55 Polegadas Hq-qled55sm 4k",
        "SMART TV LG 55 POLEGADAS QNED",
    ],
)
def teste_casamento_completo(titulo):
    assert s("smart tv 55", titulo) >= 95


@pytest.mark.parametrize(
    ("titulo", "teto"),
    [
        ('Smart TV 49" Philco UHD 4K', 40),
        ("Desodorante Rexona Aerosol Clinical 55ml", 15),
        ("Argola Curvada em Ouro Branco 18k, 55mm", 15),
        ("Tapete Higiênico Baby Slim 60X55 cm", 15),
    ],
)
def teste_falta_de_palavra_ou_numero_limita_a_nota(titulo, teto):
    assert s("smart tv 55", titulo) <= teto


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("iphone 15", "Capa para iPhone 15 Silicone"),
        ("iphone 15", "Película de Vidro iPhone 15"),
        ("smart tv 55", "Suporte De Tv Fixo Smart Tv Led 55"),
        ("tv 55", "Rack para Tv até 55 Polegadas com LED"),
        ("tv 55", "Bancada para Tv até 55 Polegadas Atlanta"),
        ("geladeira", "Motoventilador Geladeira Electrolux"),
        ("air fryer", "Botão do Timer cor Preto/Inox da Air Fryer NAF-03"),
        ("air fryer", "Cesto Redondo Antiaderente da Air Fryer Mondial"),
        ("air fryer", "Acessórios Air Fryer Electrolux Separador"),
        ("air fryer", "Limpa Air Fryer 250Ml Super Dom"),
        ("air fryer", "AIR FRYER DIVERTIDA - BS TOYS"),
        ("air fryer", "Geração Chef Jr - Air Fryer - Usual Brinquedos"),
        ("liquidificador", "Copo do Liquidificador Arno Power Max"),
        ("air fryer", "Grelha 4 Amortecedores Airfryer Walita NA130"),
        ("air fryer", "Assadeira de Silicone para Air Fryer 20cm"),
        ("air fryer", "Tapete Antiaderente Air Fryer Kit 2"),
        ("geladeira", "Pés Niveladores para Geladeira Consul"),
    ],
)
def teste_acessorios_ficam_abaixo_do_produto(consulta, titulo):
    assert s(consulta, titulo) <= 30


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("air fryer", "Fritadeira Elétrica Air Fryer Mondial 4L 110V"),
        ("air fryer", "Air Fryer Oven Britânia BAF11A"),
        ("panelas", "Jogo de Panelas Tramontina 5 Peças"),
        ("panelas", "Kit de Panelas Antiaderente"),
        ("geladeira", "Geladeira Brastemp Frost Free"),
        ("smart tv 55", "Smart TV LG de 55 Polegadas"),
        ("air fryer brinquedo", "Air Fryer de Brinquedo Divertida"),
        ("grelha eletrica", "Grelha Elétrica Mondial Smart Grill 1000W"),
        ("assadeira", "Assadeira Retangular Antiaderente Tramontina"),
    ],
)
def teste_o_proprio_produto_nao_e_confundido_com_peca(consulta, titulo):
    assert s(consulta, titulo) >= 90


def teste_busca_por_acessorio_nao_e_penalizada():
    assert s("capa iphone 15", "Capa para iPhone 15 Silicone") == 100


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("rtx 4060", "Placa de Vídeo Gigabyte GeForce RTX4060 Windforce"),
        ("rtx4060", "Placa de Vídeo MSI RTX 4060 Ventus 2X"),
        ("notebooks gamer", "Notebook Gamer Acer Nitro V15"),
        ("geladeiras inox", "Geladeira Frost Free Inox 400L"),
        ("fogões 5 bocas", "Fogão 5 Bocas Atlas"),
        ("televisao", "Televisão Samsung"),
    ],
)
def teste_codigos_plurais_e_acentos_casam(consulta, titulo):
    assert s(consulta, titulo) >= 95


def teste_numero_dentro_de_outro_numero_nao_casa():
    assert s("iphone 15", "Apple iPhone 16 Pro 256GB") <= 40
    assert s("rtx 4060", "Placa de Vídeo RTX 4070 Super") <= 40


def teste_palavras_em_ordem_valem_mais_que_espalhadas():
    assert s("smart tv 55", "Smart TV 55 Polegadas LG") == 100
    assert s("smart tv 55", "Smart TV Samsung 55 Polegadas") == 95


def teste_frase_em_sequencia_desempata_para_cima():
    perto = s("ar condicionado", "Ar Condicionado Split Inverter 12000 BTUs")
    longe = s("ar condicionado", "Condicionado de cabelo com ar")
    assert perto > longe


def teste_consulta_vazia_casa_com_tudo():
    assert s("de para", "Qualquer coisa") == 100


def teste_nota_e_limitada():
    for titulo in ["", "x", "smart tv 55 smart tv 55 smart tv 55"]:
        assert 0 <= s("smart tv 55", titulo) <= 100


@pytest.mark.parametrize(
    ("consulta", "titulo", "baixo", "alto"),
    [
        ("geladeira frost free", "Geladeira Consul Duplex Cycle Defrost 334L", 0, 69),
        ("geladeira frost free", "Geladeira Consul Frost Free 337 CRB39MK", 95, 100),
        ("micro-ondas 20 litros", "Fusivel Ceramica 6X30 20A Para Microondas 02Pcs", 0, 30),
        ("micro-ondas 20 litros", "Micro-Ondas Midea 20L Mastercook MHP20B Branco", 95, 100),
        ("micro-ondas 20 litros", "Microondas Mastercook 20 Litros Midea", 95, 100),
        ("notebook i5", "PC Básico i5 4590 H81 8GB DDR3 SSD 240GB", 0, 69),
        ("notebook i5", "Notebook Dell Latitude 5470 Intel Core i5 8GB", 95, 100),
        ("notebook i5", "Notebook HP Probook Intel Core I5-6300u 8GB", 95, 100),
        ("air fryer", "Cozinha Divertida Air Fryer com Alimentos e Acessórios", 0, 30),
        ("air fryer", "Fritadeira Airfryer Mondial 4L", 95, 100),
        ("fone bluetooth jbl", "Fone de Ouvido Bluetooth Vinik Easy W1+ TWS", 0, 69),
        ("smart tv 55", 'Smart TV LG 55" 4K UHD', 95, 100),
        ("tv 55 polegadas", 'Smart TV LG 55" 4K UHD', 95, 100),
        ("galaxy s23", "Smartphone Samsung Galaxy S23 256GB", 95, 100),
        ("galaxy s23", "Smartphone Samsung Galaxy S24 256GB", 0, 69),
    ],
)
def teste_regressoes_de_buscas_reais(consulta, titulo, baixo, alto):
    assert baixo <= s(consulta, titulo) <= alto


def teste_unidades_e_codigos_se_separam_igual():
    from app.relevancia import termos_do_texto

    assert termos_do_texto("Micro-ondas 20L 110V 4K") == (
        "microondas",
        "20",
        "l",
        "110",
        "v",
        "4",
        "k",
    )
    assert termos_do_texto("Core i5 Galaxy S23 RTX4060") == (
        "core",
        "i5",
        "galaxy",
        "s23",
        "rtx",
        "4060",
    )
    assert termos_do_texto('TV 55" e 20 litros') == ("tv", "55", "pol", "e", "20", "l")


def teste_vendedor_de_brinquedo_nao_e_o_produto():
    from app.relevancia import pontuar_com_vendedor

    q = interpretar_consulta("air fryer")
    titulo = "Mini Cozinha - Air Fryer com Luz e Som - Fenix"
    assert pontuar_com_vendedor(q, titulo, "MP Brinquedos") <= 30
    assert pontuar_com_vendedor(q, "Fritadeira Air Fryer Mondial", "Mondial Store") >= 95
    assert (
        pontuar_com_vendedor(interpretar_consulta("air fryer brinquedo"), titulo, "MP Brinquedos")
        >= 60
    )


def teste_nota_de_loja_de_brinquedo_respeita_busca_por_brinquedo():
    from app.relevancia import pontuar_loja_brinquedos

    assert pontuar_loja_brinquedos(interpretar_consulta("geladeira"), 100) == 60
    assert pontuar_loja_brinquedos(interpretar_consulta("geladeira brinquedo"), 100) == 100


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("estante multy menta", "Estante 4 Prateleiras Multy Artely Menta Peça"),
        ("comoda branca", "Cômoda 4 Gavetas Branca Atualle"),
        ("estante livros multy 4 prateleiras", "Estante Livros 4 Prateleiras Multy Menta"),
    ],
)
def teste_quantidade_de_prateleiras_e_gavetas_descreve_o_movel(consulta, titulo):
    assert s(consulta, titulo) >= 90


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("iphone", "iPhone 13 Capa Silicone Preta"),
        ("iphone 13", "Kit 2 Capas para iPhone 13"),
        ("geladeira", "Prateleira 2 Gavetas para Geladeira"),
    ],
)
def teste_numero_antes_de_peca_nao_livra_acessorio(consulta, titulo):
    assert s(consulta, titulo) <= 30


@pytest.mark.parametrize(
    ("titulo", "baixo", "alto"),
    [
        ("Estante Para Livros Com 4 Prateleiras Multy Menta Artely Menta", 95, 100),
        ("Estante para Livros 5 Prateleiras Multy Menta", 0, 40),
        ("Estante Para Livros Com 4 Prateleiras Multy Branco Artely Branco", 0, 40),
        ("Estante Multy Verde Menta", 0, 69),
    ],
)
def teste_estante_multy_menta_respeita_modelo_cor_e_prateleiras(titulo, baixo, alto):
    assert baixo <= s("estante para livros multy 4 prateleiras menta", titulo) <= alto


def teste_cor_diferente_da_pedida_fica_escondida():
    assert s("geladeira inox", "Geladeira Brastemp Frost Free Branca") <= 40
    assert s("geladeira inox", "Geladeira Brastemp Frost Free 375L") > 40
    assert s("tenis preto", "Tênis Olympikus Preto e Branco") >= 95


def teste_numero_por_extenso_casa_com_o_digito():
    assert s("estante multy quatro prateleiras", "Estante 4 Prateleiras Multy Artely") >= 95
    assert s("fogao cinco bocas", "Fogão 5 Bocas Atlas") >= 95


@pytest.mark.parametrize(
    ("consulta", "titulo", "ausentes"),
    [
        ("estante multy menta", "Estante Multy Menta Artely", []),
        (
            "estante para livros multy 4 prateleiras menta",
            "Estante Multy 5 Prateleiras Branca",
            ["livros", "4 prateleiras", "menta"],
        ),
        ("geladiera frost free", "Geladeira Consul Duplex", ["frost free"]),
        ("maquina de lavar louça", "Geladeira Brastemp", ["máquina de lavar louça"]),
        ("geladeira inox 110v", "Geladeira Inox 220V", ["110v"]),
        ("jogo de panelas", "Frigideira Tramontina", ["jogo de panelas"]),
    ],
)
def teste_termos_ausentes_usam_as_palavras_da_busca(consulta, titulo, ausentes):
    from app.relevancia import termos_ausentes

    assert termos_ausentes(interpretar_consulta(consulta), titulo) == ausentes


@pytest.mark.parametrize(
    ("consulta", "titulo", "baixo", "alto"),
    [
        ("geladeira inox 110v", "Geladeira Consul Frost Free 337L Inox 127V", 95, 100),
        ("geladeira inox 110v", "Geladeira Consul Frost Free Inox Bivolt", 95, 100),
        ("geladeira inox 110v", "Geladeira Consul Frost Free Inox 220V", 0, 40),
        ("furadeira de impacto 220v", "Furadeira de Impacto Bosch 127/220V", 95, 100),
        ("furadeira de impacto 220v", "Furadeira de Impacto Bosch 127V", 0, 40),
        ("geladeira 127v", "Geladeira Brastemp 110 Volts", 95, 100),
    ],
)
def teste_voltagem_pedida_aceita_127_e_bivolt(consulta, titulo, baixo, alto):
    assert baixo <= s(consulta, titulo) <= alto


def teste_unidade_sozinha_nao_conta_como_palavra_achada():
    assert s("iphone 15 128gb", "Notebook Lenovo 15.6 SSD 128GB") <= 15
    assert s("geladeira 110v", "Ventilador de Mesa 110V") <= 15
    assert s("tv 55 pol", "Smart TV LG 55 Polegadas") >= 95


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("iphone 15 128gb", "Apple iPhone 15 Pro 128GB Titânio"),
        ("capinha iphone 13", "Capinha Para Iphone 13 Pro Max Acrílica"),
        ("iphone 13 pro", "iPhone 13 Pro Max 256GB"),
        ("galaxy s23", "Samsung Galaxy S23 Ultra 256GB"),
    ],
)
def teste_versao_do_modelo_que_nao_foi_pedida_fica_escondida(consulta, titulo):
    assert s(consulta, titulo) <= 40


@pytest.mark.parametrize(
    ("consulta", "titulo"),
    [
        ("iphone 15 pro", "Apple iPhone 15 Pro 128GB"),
        ("capinha iphone 13", "Capa Capinha Para iPhone 13/13 Pro/13 Pro Max Silicone"),
        ("galaxy s23 ultra", "Samsung Galaxy S23 Ultra 256GB"),
    ],
)
def teste_versao_pedida_ou_compativel_continua(consulta, titulo):
    assert s(consulta, titulo) >= 95


def teste_tom_da_cor_pedida_casa_mas_o_contrario_nao():
    menta = "Estante Para Livros Com 4 Prateleiras Multy Menta Artely"
    assert s("livreiro multy verde", menta) >= 95
    assert s("estante multy menta", "Estante Multy Verde") <= 40


def teste_bt_e_bluetooth():
    assert s("caixa de som bluetooth", "Caixa de Som Xplode 4 50W BT/AUX/USB Pulse") >= 95


def teste_loja_de_brinquedo_nao_perde_nota_em_busca_de_brinquedo():
    from app.relevancia import pontuar_loja_brinquedos

    assert pontuar_loja_brinquedos(interpretar_consulta("lego star wars"), 100) == 100
    assert pontuar_loja_brinquedos(interpretar_consulta("carrinho hot wheels"), 100) == 100
    assert pontuar_loja_brinquedos(interpretar_consulta("garrafa termica"), 100) == 60
