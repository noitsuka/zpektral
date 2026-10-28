from typing import NamedTuple


class Sinonimo(NamedTuple):
    termo: str
    nas_lojas: str | None
    formas: tuple[str, ...]


SINONIMOS = (
    Sinonimo(
        "lavaloucas",
        "lava-louças",
        (
            "lava louças",
            "lavalouças",
            "lavadora de louças",
            "máquina de lavar louças",
            "máquina de lavar pratos",
        ),
    ),
    Sinonimo(
        "lavaeseca",
        None,
        ("lava e seca", "lava seca", "lavadora e secadora", "lavadora secadora"),
    ),
    Sinonimo(
        "lavadorapressao",
        None,
        ("lavadora de alta pressão", "lavadora alta pressão", "lavadora de pressão"),
    ),
    Sinonimo(
        "lavadora",
        "máquina de lavar",
        (
            "lavadora",
            "lavadora de roupas",
            "máquina de lavar",
            "máquina de lavar roupas",
        ),
    ),
    Sinonimo("geladeira", "geladeira", ("geladeira", "refrigerador")),
    Sinonimo(
        "microondas",
        "micro-ondas",
        ("micro-ondas", "microondas", "forno micro-ondas", "forno de micro-ondas"),
    ),
    Sinonimo(
        "airfryer",
        "air fryer",
        ("air fryer", "airfryer", "fritadeira sem óleo", "fritadeira elétrica sem óleo"),
    ),
    Sinonimo("arcondicionado", None, ("ar condicionado", "arcondicionado")),
    Sinonimo("celular", None, ("celular", "smartphone", "telefone celular")),
    Sinonimo("notebook", None, ("notebook", "laptop")),
    Sinonimo("tv", None, ("tv", "smart tv", "televisão", "televisor")),
    Sinonimo(
        "fone",
        None,
        ("fone", "fone de ouvido", "headphone", "headset", "earphone", "earbuds"),
    ),
    Sinonimo("console", None, ("console", "videogame", "video game")),
    Sinonimo("cafeteira", None, ("cafeteira", "máquina de café")),
    Sinonimo("roboaspirador", None, ("robô aspirador", "aspirador robô")),
)

PALAVRAS_DE_PRODUTO = """
    geladeira refrigerador freezer fogão fogões cooktop forno coifa depurador micro-ondas
    microondas máquina máquinas lavar louça louças roupa roupas lavadora secadora lava seca
    ventilador ventiladores circulador climatizador aquecedor condicionado aspirador robô pó
    liquidificador batedeira cafeteira fritadeira panela panelas pressão elétrica elétrico
    sanduicheira torradeira chaleira espremedor processador mixer grill purificador bebedouro
    água colchão colchões travesseiro cama box sofá poltrona cadeira cadeiras mesa escrivaninha
    armário guarda-roupa cômoda estante rack painel televisão televisor celular smartphone
    notebook computador monitor teclado impressora tablet fone ouvido caixa som câmera
    relógio smartwatch videogame console controle tênis bicicleta patinete esteira halteres
    perfume shampoo condicionador hidratante protetor fralda fraldas chuveiro ferro passar
    secador cabelo prancha barbeador depilador escova dental furadeira parafusadeira serra
    ferramentas lâmpada luminária inox branco branca preto preta vidro
    polegadas litros bocas portas serviços programas velocidades frost free duplex inverter
    portátil digital automático automática infantil masculino feminino
"""
