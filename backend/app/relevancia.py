import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib import resources
from itertools import pairwise

from app.modelos import voltagem_do_titulo
from app.sinonimos import PALAVRAS_DE_PRODUTO, SINONIMOS, Sinonimo

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
_CONTAGEM = re.compile(r"\b(?:[2-9]|[1-9]\d) ([a-z]+s)\b")
_LETRA_DIGITO = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_MARCA_POLEGADA = re.compile(r"(\d)\s*(?:\"|\u201d|'')")
_ORDINAL = re.compile(r"(\d)\s*[\u00aa\u00ba\u00b0]")
# "12.000 BTUs" é milhar; "10,1kg" e "6,1 pol" são decimais e valem pela parte inteira
_MILHAR = re.compile(r"(\d)\.(\d{3})(?!\d)")
_DECIMAL = re.compile(r"(\d)[.,]\d{1,2}(?!\d)")
# tela de 23,8" é vendida como de 24 polegadas
_POLEGADA_DECIMAL = re.compile(r"(\d+)[.,](\d)\d?(?=\s*pol)", re.I)
# "Galaxy S24+" é a versão Plus; "A+++" vira "a plus", sem efeito
_MAIS = re.compile(r"(?<=[0-9A-Za-z])\++(?![0-9A-Za-z])")

PALAVRAS_VAZIAS = frozenset(
    "a o as os de da do das dos e em no na nos nas com sem para por pra p um uma the".split()
)

# dizem o que a pessoa quer pagar, não o produto: em "geladeira barata", nenhuma geladeira
# trazia "barata" no título e todas sumiam, e a loja que buscava a frase devolvia inseticida
PALAVRAS_DE_INTENCAO = frozenset("barato barata promocao oferta desconto melhor".split())

PALAVRAS_ACESSORIO = frozenset(
    """
    capa capinha case pelicula protetor suporte cabo carregador adaptador fonte skin adesivo
    bolsa mochila maleta estojo base refil filtro peca borracha gaxeta prateleira gaveta
    puxador motoventilador termostato resistencia controle pulseira tampa painel rack
    acessorio cesto cuba botao copo jarra lamina helice mangueira valvula bico vedacao
    engrenagem correia parafuso rodizio limpa limpador fusivel lampada grelha
    amortecedor tapete assadeira pe pes bandeja forma papel oculo interruptor gatilho volante
    wheel bocal extensor
    jogo game midia pad control cartucho toner bateria tela broca bit ponteira lixa
    """.split()
)

# depois do nome do produto, descrevem o próprio produto ("Air Fryer Cesto Quadrado")
PARTES_DESCRITIVAS = frozenset(
    "cesto copo jarra base controle painel grelha tampa lampada gaveta prateleira "
    "bandeja forma pe resistencia jogo game pad control cartucho toner bateria tela "
    "broca bit ponteira lixa".split()
)
# título dividido por " - ": "Pay Day 3 - PS5" é um jogo para o PS5, não o PS5
_SEPARADOR = re.compile(r"\s[-\u2013|]\s")
INSPIRADOS = frozenset("inspirado inspirada inspired contratipo".split())
PALAVRAS_PARA = frozenset({"para", "pra", "p", "compativel", "compat", "compatible", "for"})
PARTE_DE = frozenset({"de", "da", "do", "das", "dos"})
COLETIVOS = frozenset({"jogo", "kit", "conjunto", "par", "combo", "caixa", "pacote", "linha"})
PALAVRAS_BRINQUEDO = frozenset(
    {"brinquedo", "toy", "infantil", "kid", "miniatura", "jr", "divertido", "divertida"}
)
# só na busca: quem pede um destes quer o brinquedo, e a loja de brinquedos não perde nota
BUSCA_DE_BRINQUEDO = frozenset(
    "lego barbie boneca boneco pelucia playmobil nerf wheel massinha puzzle".split()
)
VERSOES_DE_MODELO = frozenset("pro max promax mini plus ultra fe lite".split())
TENSOES = frozenset({"110", "127", "220"})
TONS = {"menta": "verde", "grafite": "cinza", "chumbo": "cinza"}

EQUIVALENTES = {
    "litro": "l",
    "lt": "l",
    "polegada": "pol",
    "volt": "v",
    "watt": "w",
    "dois": "2",
    "duas": "2",
    "tres": "3",
    "quatro": "4",
    "cinco": "5",
    "seis": "6",
    "sete": "7",
    "oito": "8",
    "nove": "9",
    "dez": "10",
    "branca": "branco",
    "preta": "preto",
    "vermelha": "vermelho",
    "amarela": "amarelo",
    "dourada": "dourado",
    "prateado": "prata",
    "prateada": "prata",
    "roxa": "roxo",
    "bt": "bluetooth",
    "btus": "btu",
    "gaming": "gamer",
    "white": "branco",
    "black": "preto",
    "silver": "prata",
    "gray": "cinza",
    "grey": "cinza",
    "blue": "azul",
    "red": "vermelho",
    "green": "verde",
    "pink": "rosa",
    "gold": "dourado",
}
CORES = frozenset(
    """
    branco preto cinza prata dourado rosa azul verde vermelho amarelo laranja roxo lilas bege
    marrom menta grafite inox nude caramelo vinho creme cobre bronze turquesa coral chumbo
    carvalho nogueira freijo cinamomo imbuia castanho
    """.split()
)
# o que algumas lojas põem no campo de marca quando não há marca
MARCAS_VAZIAS = frozenset(
    {
        "nao disponivel",
        "nao informado",
        "generico",
        "generica",
        "sem marca",
        "outros",
        "outras",
        "diversos",
        "n a",
    }
)
PISO_ESPECIFICACAO = 72  # o site esconde abaixo de 70 e só cota frete a partir de 65
# na consulta pela raridade, a palavra típica das buscas (em ~1% dos títulos) pesa perto de 1,
# como na nota principal; o número segue com peso 2
ESCALA_DA_RARIDADE = 5.0
RELEVANCIA_PRINCIPAL = 90  # daqui para cima o site mostra a oferta entre as principais
QUEDA_DE_OUTRO_PRODUTO = 8
LETRAS_UNIDADE = frozenset("lvwkgx")
UNIDADES = LETRAS_UNIDADE | frozenset("gb tb mb kg ml mm cm m hz ghz mah pol btu".split())


@lru_cache(maxsize=65_536)
def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(car for car in texto if not unicodedata.combining(car))
    return _NAO_ALFANUMERICO.sub(" ", texto).strip()


def _singular(termo: str) -> str:
    if termo.endswith("us"):  # plus, bonus, onibus
        return termo
    if len(termo) > 4 and termo.endswith("oes"):
        return termo[:-3] + "ao"
    if len(termo) > 4 and termo.endswith("es") and termo[-3] in "rsz":
        return termo[:-2]
    if len(termo) > 3 and termo.endswith("s") and not termo[-2].isdigit():
        return termo[:-1]
    return termo


def _separar_codigo(termo: str) -> list[str]:
    partes = _LETRA_DIGITO.sub(" ", termo).split()
    if len(partes) == 1:
        return partes
    curto = [p for p in partes if len(p) == 1 and not p.isdigit()]
    if all(p in LETRAS_UNIDADE for p in curto):
        return partes
    return [termo]


def _termos_brutos(texto: str) -> list[str]:
    saida = []
    texto = _ORDINAL.sub(r"\1 ", _MARCA_POLEGADA.sub(r"\1 pol ", _MAIS.sub(" plus ", texto)))
    texto = _POLEGADA_DECIMAL.sub(lambda m: str(int(m[1]) + (int(m[2]) >= 5)), texto)
    texto = _DECIMAL.sub(r"\1", _MILHAR.sub(r"\1\2", texto))
    for bruto in normalizar(texto).split():
        for peca in _separar_codigo(bruto):
            palavra = EQUIVALENTES.get(peca) or _singular(peca)
            saida.append(EQUIVALENTES.get(palavra, palavra))
    return saida


_FORMAS: dict[tuple[str, ...], Sinonimo] = {
    tuple(_termos_brutos(forma)): s for s in SINONIMOS for forma in s.formas
}
_MAIOR_FORMA = max(map(len, _FORMAS))


def _sinonimos_em(termos: list[str]) -> list[tuple[int, int, Sinonimo]]:
    achados, i = [], 0
    while i < len(termos):
        for tamanho in range(min(_MAIOR_FORMA, len(termos) - i), 0, -1):
            if sinonimo := _FORMAS.get(tuple(termos[i : i + tamanho])):
                achados.append((i, i + tamanho, sinonimo))
                i += tamanho
                break
        else:
            i += 1
    return achados


_VOCABULARIO = {
    chave: palavra
    for palavra in [
        *PALAVRAS_DE_PRODUTO.split(),
        *(p for s in SINONIMOS for forma in s.formas for p in forma.split()),
    ]
    if " " not in (chave := normalizar(palavra))
}
# gerada por scripts/gerar_palavras.py a partir de títulos reais: o corretor não mexe nelas
_PALAVRAS_REAIS = frozenset(
    resources.files("app").joinpath("dados/palavras.txt").read_text("utf-8").split()
)


_TECLADO = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_TECLA = {
    c: (linha, coluna + linha / 2)
    for linha, teclas in enumerate(_TECLADO)
    for coluna, c in enumerate(teclas)
}


def _troca(a: str, b: str) -> int:
    if a == b:
        return 0
    (la, ca), (lb, cb) = _TECLA.get(a, (9, 0)), _TECLA.get(b, (-9, 0))
    vizinhas = (la == lb and abs(ca - cb) == 1) or (abs(la - lb) == 1 and abs(ca - cb) <= 0.5)
    return 1 if vizinhas else 2


def _distancia(a: str, b: str) -> int:
    anterior2: list[int] = []
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            custo = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + _troca(ca, cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                custo = min(custo, anterior2[j - 2] + 1)
            atual.append(custo)
        anterior2, anterior = anterior, atual
    return anterior[-1]


@lru_cache(maxsize=4096)
def _corrigir_palavra(palavra: str) -> str:
    chave = normalizar(palavra)
    if not chave or " " in chave or any(c.isdigit() for c in chave):
        return palavra
    if (certa := _VOCABULARIO.get(chave)) is not None:
        return palavra if palavra.casefold() == certa else certa
    if len(chave) < 6 or chave in _PALAVRAS_REAIS:
        return palavra
    limite = 2 if len(chave) >= 9 else 1
    distancias = {
        certa: _distancia(conhecida, chave)
        for conhecida, certa in _VOCABULARIO.items()
        if conhecida[0] == chave[0] and abs(len(conhecida) - len(chave)) <= limite
    }
    proximas = [certa for certa, d in distancias.items() if d <= limite]
    if not proximas:
        return palavra
    menor = min(distancias[c] for c in proximas)
    melhores = [c for c in proximas if distancias[c] == menor]
    return melhores[0] if len(melhores) == 1 else palavra


def corrigir(texto: str) -> str:
    return " ".join(_corrigir_palavra(palavra) for palavra in texto.split())


@lru_cache(maxsize=65_536)
def termos_do_texto(texto: str) -> tuple[str, ...]:
    termos = _termos_brutos(texto)
    for inicio, fim, sinonimo in reversed(_sinonimos_em(termos)):
        termos[inicio:fim] = [sinonimo.termo]
    return tuple(termos)


def _brutos_por_palavra(palavras: list[str]) -> tuple[list[str], list[int]]:
    termos: list[str] = []
    dono: list[int] = []
    for i, palavra in enumerate(palavras):
        brutos = _termos_brutos(palavra)
        termos += brutos
        dono += [i] * len(brutos)
    return termos, dono


def texto_para_lojas(texto: str) -> str:
    if gtin := _gtin(texto):
        return gtin
    palavras = corrigir(texto).split()
    produto = [p for p in palavras if not _so_intencao(p)]
    if produto:
        palavras = produto
    termos, dono = _brutos_por_palavra(palavras)
    trocas = {
        dono[inicio]: (dono[fim - 1], sinonimo.nas_lojas)
        for inicio, fim, sinonimo in _sinonimos_em(termos)
        if sinonimo.nas_lojas
    }
    saida, i = [], 0
    while i < len(palavras):
        if i in trocas:
            ultima, nome = trocas[i]
            saida.append(nome)
            i = ultima + 1
        else:
            saida.append(palavras[i])
            i += 1
    return " ".join(saida)


def _so_intencao(palavra: str) -> bool:
    brutos = _termos_brutos(palavra)
    return bool(brutos) and PALAVRAS_DE_INTENCAO.issuperset(brutos)


def sem_unidade_por_extenso(texto: str) -> str:
    """Tira a unidade escrita em palavra separada depois do número: "4 litros" vira "4".

    Medido nas lojas VTEX: a busca delas acha mais produtos certos sem a unidade solta, e a
    unidade colada ao número ("128gb", "9w") rende igual ou melhor como a pessoa escreveu.
    """
    palavras = texto.split()
    return " ".join(
        p
        for i, p in enumerate(palavras)
        if not (i and palavras[i - 1][-1].isdigit() and _unidade_solta(p))
    )


def _unidade_solta(palavra: str) -> bool:
    termos = _termos_brutos(palavra)
    return len(termos) == 1 and termos[0] in UNIDADES


@dataclass(frozen=True, slots=True)
class Consulta:
    texto: str
    termos: tuple[str, ...]
    pesos: tuple[float, ...]
    pede_acessorio: bool
    gtin: str | None = None
    palavras: tuple[tuple[str, tuple[str, ...]], ...] = ()
    numeros: tuple[bool, ...] = field(init=False)
    pares: tuple[tuple[str, str, str, bool], ...] = field(init=False)
    cores: frozenset[str] = field(init=False)
    voltagem: str | None = field(init=False)
    tensao: frozenset[str] = field(init=False)
    modelos: tuple[str, ...] = field(init=False)
    unidades_pedidas: tuple[str, ...] = field(init=False)
    tipo: str | None = field(init=False)
    marcas: frozenset[str] = field(init=False)
    linhas: tuple[tuple[str, str], ...] = field(init=False)
    anos: frozenset[str] = field(init=False)
    sem: frozenset[str] = field(init=False)
    com: frozenset[str] = field(init=False)
    cabeca_e_tipo: bool = field(init=False)

    # o que só depende da consulta sai daqui uma vez, e não a cada título pontuado
    def __post_init__(self) -> None:
        termos = self.termos
        seguintes = (*termos[1:], "") if termos else ()
        pares = ((a, b, a + b) for a, b in pairwise(termos))
        numeros = tuple(map(_tem_numero, termos))
        tensao = {t for t, s in zip(termos, seguintes, strict=True) if t in TENSOES and s == "v"}
        modelos = tuple(
            t
            for t, s, n in zip(termos, seguintes, numeros, strict=True)
            if n and s not in UNIDADES and t not in tensao
        )
        object.__setattr__(self, "numeros", numeros)
        object.__setattr__(self, "pares", tuple((*p, len(p[2]) >= 6) for p in pares))
        object.__setattr__(self, "cores", CORES.intersection(termos))
        object.__setattr__(self, "voltagem", voltagem_do_titulo(self.texto) if tensao else None)
        object.__setattr__(self, "tensao", frozenset(tensao | {"v"} if tensao else ()))
        object.__setattr__(self, "modelos", modelos)
        # número com unidade (559 l, 55 pol, 256 gb): a especificação que identifica o produto
        unidades = tuple(
            s
            for t, s, n in zip(termos, seguintes, numeros, strict=True)
            if n and s in UNIDADES and t not in tensao
        )
        object.__setattr__(self, "unidades_pedidas", unidades)
        tipo = next(
            (t for t, n in zip(termos, numeros, strict=True) if not n and t in _produtos()), None
        )
        object.__setattr__(self, "tipo", tipo)
        marcas = frozenset(t for t in termos if t in _marcas())
        object.__setattr__(self, "marcas", marcas)
        # "flip 6", "iphone 15": o número do modelo só identifica junto do nome da linha
        linhas = tuple(
            (a, b)
            for (a, b), depois in zip(pairwise(termos), (*termos[2:], ""), strict=False)
            if b.isdigit()
            and b in modelos
            and (not depois or _tem_numero(depois) or depois in VERSOES_DE_MODELO)
            and a.isalpha()
            and a not in _produtos()
            and a not in CORES
            and a not in UNIDADES
            and a not in marcas
        )
        object.__setattr__(self, "linhas", linhas)
        object.__setattr__(self, "anos", frozenset(filter(_ano, modelos)))
        # "sem" e "com" são palavras vazias, mas "sem fio" e "com fio" são produtos opostos
        brutos = _termos_brutos(corrigir(self.texto))
        object.__setattr__(self, "sem", frozenset(b for a, b in pairwise(brutos) if a == "sem"))
        object.__setattr__(self, "com", frozenset(b for a, b in pairwise(brutos) if a == "com"))
        # a busca começa pelo tipo do produto ("aspirador", "controle", "notebook"), e não por
        # marca, linha ou nome ("samsung galaxy", "rtx 4060", "kimetsu no yaiba")
        cabeca = cabeca_do_titulo(termos)
        object.__setattr__(
            self,
            "cabeca_e_tipo",
            cabeca in _tipos() or cabeca in _produtos() or cabeca in PALAVRAS_ACESSORIO,
        )

    @property
    def esta_vazia(self) -> bool:
        return not self.termos


def _termos_de_cada_palavra(palavras: list[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    brutos, dono = _brutos_por_palavra(palavras)
    termos: list[list[str]] = [[] for _ in palavras]
    trechos = {inicio: (fim, s.termo) for inicio, fim, s in _sinonimos_em(brutos)}
    i = 0
    while i < len(brutos):
        fim, termo = trechos.get(i, (i + 1, brutos[i]))
        if termo not in PALAVRAS_VAZIAS:
            for j in range(dono[i], dono[fim - 1] + 1):
                termos[j].append(termo)
        i = fim
    return tuple(zip(palavras, map(tuple, termos), strict=True))


@lru_cache(maxsize=1024)
def interpretar_consulta(texto: str) -> Consulta:
    corrigido = corrigir(texto)
    termos = tuple(dict.fromkeys(t for t in termos_do_texto(corrigido) if t not in PALAVRAS_VAZIAS))
    if any(t not in PALAVRAS_DE_INTENCAO for t in termos):
        termos = tuple(t for t in termos if t not in PALAVRAS_DE_INTENCAO)
    brutos = _termos_brutos(corrigido)
    palavras_do_produto = {
        s.termo: sum(t not in PALAVRAS_VAZIAS for t in brutos[inicio:fim])
        for inicio, fim, s in _sinonimos_em(brutos)
    }
    pesos = tuple(
        2.0 if _tem_numero(t) else float(max(1, palavras_do_produto.get(t, 1))) for t in termos
    )
    especiais = (PALAVRAS_ACESSORIO | PALAVRAS_BRINQUEDO) - _contados(corrigido)
    return Consulta(
        texto,
        termos,
        pesos,
        any(t in especiais for t in termos),
        _gtin(texto),
        _termos_de_cada_palavra(corrigido.split()),
    )


def termos_ausentes(
    consulta: Consulta, titulo: str, ean: object = None, marca: str | None = None
) -> list[str]:
    if consulta.gtin and normalizar_ean(ean) == consulta.gtin:
        return []
    achados = _acertos(consulta, termos_do_texto(titulo), titulo, marca)
    trechos: list[list[str]] = []
    vazias: list[str] = []
    aberto = False
    for palavra, termos in consulta.palavras:
        termos = tuple(t for t in termos if t in consulta.termos or t not in PALAVRAS_DE_INTENCAO)
        if not termos:
            vazias.append(palavra)
            continue
        if any(t not in achados for t in termos):
            if aberto:
                trechos[-1] += [*vazias, palavra]
            else:
                trechos.append([palavra])
            aberto = True
        else:
            # um número sozinho não se explica: leva a palavra seguinte, como em "4 prateleiras"
            if aberto and not any(c.isalpha() for p in trechos[-1] for c in p):
                trechos[-1] += [*vazias, palavra]
            aberto = False
        vazias = []
    return list(dict.fromkeys(" ".join(t) for t in trechos))


def _gtin(texto: str) -> str | None:
    return next((g for p in texto.split() if 12 <= len(p) <= 14 and (g := normalizar_ean(p))), None)


@lru_cache(maxsize=65_536)
def _contados(texto: str) -> frozenset[str]:
    return frozenset(_singular(p) for p in _CONTAGEM.findall(normalizar(texto)))


def _tem_numero(termo: str) -> bool:
    return any(c.isdigit() for c in termo)


def _ano(termo: str) -> bool:
    return len(termo) == 4 and termo.isdigit() and 1990 <= int(termo) <= 2039


def _acertos(
    consulta: Consulta, palavras_titulo: tuple[str, ...], titulo: str, marca: str | None = None
) -> dict[str, int]:
    achados: dict[str, int] = {}
    posicoes: dict[str, int] = {}
    for i, t in enumerate(palavras_titulo):
        posicoes.setdefault(t, i)
    for termo in consulta.termos:
        if termo in posicoes:
            achados[termo] = posicoes[termo]
    for a, b, par, prefixo in consulta.pares:
        if a in achados and b in achados:
            continue
        for i, t in enumerate(palavras_titulo):
            if t == par or (prefixo and t.startswith(par)):
                achados.setdefault(a, i)
                achados.setdefault(b, i)
                break
    faltam = [t for t in consulta.termos if t not in achados and len(t) >= 4]
    if faltam:
        colado = "".join(palavras_titulo)
        for termo in faltam:
            if termo in colado and not any(termo in t for t in palavras_titulo):
                achados[termo] = len(palavras_titulo)
    # 127 V é a tensão de 110 V, e bivolt serve para as duas
    if (
        consulta.tensao
        and not consulta.tensao <= achados.keys()
        and voltagem_do_titulo(titulo) in (consulta.voltagem, "bivolt")
    ):
        for termo in consulta.tensao:
            achados.setdefault(termo, len(palavras_titulo))
    for tom, cor in TONS.items():
        if cor in consulta.cores and cor not in achados and tom in posicoes:
            achados[cor] = posicoes[tom]
    # a marca pedida vem no campo de marca da loja, não no título ("Lavadora 11kg LES11")
    if marca and consulta.marcas:
        for termo in consulta.marcas.intersection(termos_do_texto(marca)):
            achados.setdefault(termo, len(palavras_titulo))
    return achados


def _outra_versao(consulta: Consulta, palavras_titulo: tuple[str, ...]) -> bool:
    for modelo in consulta.modelos:
        lugares = [i for i, t in enumerate(palavras_titulo) if t == modelo]
        if lugares and all(_versao_nao_pedida(consulta, palavras_titulo[i + 1 :]) for i in lugares):
            return True
    return False


def _versao_nao_pedida(consulta: Consulta, seguintes: tuple[str, ...]) -> bool:
    for t in seguintes:
        if t not in VERSOES_DE_MODELO:
            return False
        if t not in consulta.termos:
            return True
    return False


def pontuar(consulta: Consulta, titulo: str, marca: str | None = None) -> int:
    if consulta.esta_vazia:
        return 100
    palavras_titulo = termos_do_texto(titulo)
    achados = _acertos(consulta, palavras_titulo, titulo, marca)

    casado = 0.0
    total = sum(consulta.pesos)
    falta_numero = False
    palavras, palavras_achadas = 0, 0
    primeira_palavra = len(palavras_titulo)
    for termo, peso, numero in zip(consulta.termos, consulta.pesos, consulta.numeros, strict=True):
        consumir = termo in achados
        if not numero and termo not in UNIDADES:
            palavras += 1
            palavras_achadas += consumir
            if consumir:
                primeira_palavra = min(primeira_palavra, achados[termo])
        if consumir:
            casado += peso
        # o ano que o anúncio não traz não é outro modelo ("camisa do corinthians 2024"); outro
        # ano no título, sim
        elif numero and not (termo in consulta.anos and not any(map(_ano, palavras_titulo))):
            falta_numero = True

    resultado = casado / total * 95
    # A especificação pedida (559 l, 55 pol) e o tipo de produto estão no título: o que falta são
    # palavras que o anúncio não repetiu, como "frost free" no da própria Brastemp. A oferta fica
    # acima do corte do site, como parecida e com o que faltou indicado; as regras abaixo ainda a
    # derrubam se for outra cor, outra versão ou um acessório.
    if (
        consulta.unidades_pedidas
        and not falta_numero
        and consulta.tipo in achados
        and all(u in achados for u in consulta.unidades_pedidas)
    ):
        resultado = max(resultado, PISO_ESPECIFICACAO)
    if consulta.cores and (no_titulo := CORES.intersection(palavras_titulo)):
        familias = no_titulo | {TONS[c] for c in no_titulo & TONS.keys()}
        if not consulta.cores & familias:
            resultado = min(resultado, 40)
    # outra marca: quem pediu Electrolux não procura a Midea entre os parecidos
    if (
        consulta.marcas
        and not consulta.marcas & achados.keys()
        and _tem_marca(palavras_titulo, marca)
    ):
        resultado = min(resultado, 40)
    if (
        falta_numero
        or _quantidade_trocada(consulta.termos, palavras_titulo)
        or any(n in achados and linha not in achados for linha, n in consulta.linhas)
    ):
        resultado = min(resultado, 40)
    if palavras and not palavras_achadas:
        resultado = min(resultado, 15)

    if casado == total:
        frase = " ".join(t for t in palavras_titulo if t not in PALAVRAS_VAZIAS)
        if len(consulta.termos) == 1 or " ".join(consulta.termos) in frase:
            resultado += 5
    # todos os termos casam, mas o título é outra versão do modelo ("15 pro" para "iphone 15")
    if consulta.modelos and _outra_versao(consulta, palavras_titulo):
        resultado = min(resultado, 40)
    # pediu "sem fio" e o título diz "com fio", ou o contrário
    if consulta.sem or consulta.com:
        pares_titulo = set(pairwise(palavras_titulo))
        if any(("com", p) in pares_titulo for p in consulta.sem) or any(
            ("sem", p) in pares_titulo for p in consulta.com
        ):
            resultado = min(resultado, 40)

    if (
        not consulta.pede_acessorio
        and casado
        and eh_secundario(palavras_titulo, primeira_palavra, consulta, titulo)
    ):
        resultado *= 0.3
    # Quem começa a busca pelo tipo do produto ("controle dualsense", "notebook dell") quer
    # esse produto: o título que abre com outro ("Capa Controle Dualsense", "Teclado Notebook
    # Para Dell") casa todas as palavras e, mais barato, ficava em primeiro. Ele cede o lugar
    # sem sair da lista principal; se a busca começa por marca ou nome ("samsung galaxy a55",
    # "kimetsu no yaiba"), não há como saber qual tipo é o produto e nada muda.
    if (
        resultado >= RELEVANCIA_PRINCIPAL
        and consulta.cabeca_e_tipo
        and abre_com_outro_tipo(consulta, titulo)
    ):
        resultado = max(RELEVANCIA_PRINCIPAL, resultado - QUEDA_DE_OUTRO_PRODUTO)
    return round(resultado)


@lru_cache(maxsize=65_536)
def _pares(termos: tuple[str, ...]) -> frozenset[tuple[str, str]]:
    # a voltagem tem regra própria: 110 e 127 valem o mesmo
    return frozenset(
        (a, b) for a, b in pairwise(termos) if a.isdigit() and b.isalpha() and b != "v"
    )


def _quantidade_trocada(termos: tuple[str, ...], palavras_titulo: tuple[str, ...]) -> bool:
    # "12 kg" pedido e o título traz "14 kg": o 12 que aparece é de outra coisa
    do_titulo = _pares(palavras_titulo)
    unidades = {b for _, b in do_titulo}
    return any(b in unidades and (a, b) not in do_titulo for a, b in _pares(termos))


def normalizar_ean(bruto: object) -> str | None:
    if not isinstance(bruto, str | int):
        return None
    digitos = str(bruto).strip()
    if not digitos.isdigit() or not 8 <= len(digitos) <= 14:
        return None
    gtin = digitos.zfill(14)
    if len(set(gtin.lstrip("0"))) <= 1:
        return None
    soma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(gtin[:-1])))
    if (10 - soma % 10) % 10 != int(gtin[-1]):
        return None
    return gtin.lstrip("0").zfill(13)


def eh_secundario(
    palavras_titulo: tuple[str, ...],
    primeiro_acerto: int,
    consulta: Consulta,
    titulo: str,
) -> bool:
    if any(
        t in PALAVRAS_ACESSORIO
        and not (i > primeiro_acerto and (t in PARTES_DESCRITIVAS or t in _contados(titulo)))
        # "jogo de panelas" é um conjunto do próprio produto
        and not (t in COLETIVOS and palavras_titulo[i + 1 : i + 2] in (("de",), ("com",)))
        for i, t in enumerate(palavras_titulo[:3])
    ):
        return True
    antes = palavras_titulo[:primeiro_acerto]
    if any(t in PALAVRAS_PARA for t in antes):
        return True
    if (
        0 < primeiro_acerto < len(palavras_titulo)
        and palavras_titulo[primeiro_acerto - 1] in PARTE_DE
        and palavras_titulo[0] not in consulta.termos
        and palavras_titulo[0] not in COLETIVOS
    ):
        return True
    if "midia" in palavras_titulo or _so_no_sufixo(titulo, consulta):
        return True
    # "Inspired by La Vie Est Belle" é outro perfume, a não ser que a busca peça o inspirado
    if not INSPIRADOS.isdisjoint(palavras_titulo) and INSPIRADOS.isdisjoint(consulta.termos):
        return True
    return any(t in PALAVRAS_BRINQUEDO for t in palavras_titulo)


def _tem_marca(palavras_titulo: tuple[str, ...], marca: str | None) -> bool:
    # a marca informada pela loja vale mesmo fora da lista ("3Green")
    return not _marcas().isdisjoint(palavras_titulo) or bool(
        marca and normalizar(marca) and normalizar(marca) not in MARCAS_VAZIAS
    )


@lru_cache(maxsize=1)
def _marcas() -> frozenset[str]:
    # gerada por scripts/gerar_marcas.py a partir de produtos reais
    bruto = resources.files("app").joinpath("dados/marcas.txt").read_text("utf-8")
    return frozenset(bruto.split()) - _produtos()


@lru_cache(maxsize=1)
def _frequencias() -> tuple[int, dict[str, int]]:
    # gerada por scripts/gerar_frequencias.py: em quantos títulos reais cada termo aparece
    arquivo = resources.files("app").joinpath("dados/frequencias.txt")
    total, *linhas = arquivo.read_text("utf-8").split()
    pares = zip(linhas[::2], linhas[1::2], strict=True)
    return int(total), {termo: int(n) for termo, n in pares}


@lru_cache(maxsize=1024)
def consulta_pela_raridade(texto: str) -> Consulta:
    """A mesma consulta, com cada palavra pesando pela raridade nos títulos reais.

    A nota principal exige todas as palavras: cada uma é um pedido, e a coleira para gatos não
    serve a quem pediu "coleira antipulgas cachorro". Quando quase nenhuma loja tem o produto
    exato, a busca se reavalia por esta: em "mangá punpun", "punpun" está em 1 de 79 mil
    títulos e "manga" em 1.500, junto de camisetas de manga curta e sucos de manga, e o volume
    de Boa Noite Punpun, que não repete "mangá", passa à frente da camiseta.
    """
    consulta = interpretar_consulta(texto)
    pesos = tuple(
        p if _tem_numero(t) else p * _peso_da_palavra(t)
        for t, p in zip(consulta.termos, consulta.pesos, strict=True)
    )
    return replace(consulta, pesos=pesos)


@lru_cache(maxsize=4096)
def _peso_da_palavra(termo: str) -> float:
    # a raridade (IDF) entra ao quadrado para o nome raro pesar várias vezes a palavra comum
    total, contagem = _frequencias()
    raridade = math.log((total + 1) / (contagem.get(termo, 0) + 1)) / math.log(total + 1)
    peso = ESCALA_DA_RARIDADE * raridade**2
    # a marca costuma ficar implícita no nome da linha ("Moto G85", "Galaxy S24") e a marca
    # errada já tem trava própria: ela não pesa mais que uma palavra comum
    return min(peso, 1.0) if termo in _marcas() else peso


def parcial_de_nome_raro(consulta: Consulta, titulo: str, ausentes: list[str]) -> bool:
    """O título traz um nome raro da busca e só não traz outro, que a loja pode escrever de
    outro jeito: "Boa Noite Punpun" em "oyasumi punpun".

    Faltar palavra comum ("boneco") não conta, e casar só a parte comum também não: em
    "graphic novel sandman", outra graphic novel não serve.
    """
    _, contagem = _frequencias()

    def raro(t: str) -> bool:
        return t not in contagem and not _tem_numero(t)

    faltaram = [t for t in termos_do_texto(" ".join(ausentes)) if t not in PALAVRAS_VAZIAS]
    trouxe = set(termos_do_texto(titulo)) & {t for t in consulta.termos if raro(t)}
    return bool(faltaram) and all(map(raro, faltaram)) and bool(trouxe)


@lru_cache(maxsize=1)
def _tipos() -> frozenset[str]:
    # gerada por scripts/gerar_frequencias.py: palavras que quase sempre abrem o título
    return frozenset(resources.files("app").joinpath("dados/tipos.txt").read_text("utf-8").split())


def cabeca_do_titulo(termos: tuple[str, ...]) -> str | None:
    return next((t for t in termos if t not in PALAVRAS_VAZIAS and t not in COLETIVOS), None)


def abre_com_outro_tipo(consulta: Consulta, titulo: str) -> bool:
    """O título abre com um tipo de produto que a busca não pediu: "Caneca Demon Slayer",
    "Bola de Futebol Seleção Brasileira". Só serve onde o sinônimo não visto custa pouco: a
    sandália Havaianas é o chinelo pedido, e a lista não sabe disso."""
    cabeca = cabeca_do_titulo(termos_do_texto(titulo))
    if cabeca in consulta.termos or (cabeca not in _tipos() and cabeca not in PALAVRAS_ACESSORIO):
        return False
    # "Livro - Boa Noite Punpun - Vol. 5": a categoria sozinha antes do separador é rótulo da
    # loja, e o produto é o que vem depois
    rotulo = _SEPARADOR.split(titulo, maxsplit=1)
    return not (len(rotulo) == 2 and termos_do_texto(rotulo[0]) == (cabeca,))


@lru_cache(maxsize=1)
def _produtos() -> frozenset[str]:
    return frozenset(termos_do_texto(PALAVRAS_DE_PRODUTO))


def _so_no_sufixo(titulo: str, consulta: Consulta) -> bool:
    # o termo buscado só aparece depois do último separador e o começo não nomeia um
    # produto: o título é de outra coisa feita para o que foi buscado
    partes = _SEPARADOR.split(titulo)
    if len(partes) < 2:
        return False
    cabeca = set(termos_do_texto(" ".join(partes[:-1]))) - PALAVRAS_VAZIAS
    termos = set(consulta.termos)
    return (
        len(cabeca) >= 2
        and not termos & cabeca
        and bool(termos & set(termos_do_texto(partes[-1])))
        and not _produtos() & cabeca
    )


def pontuar_com_vendedor(
    consulta: Consulta, titulo: str, vendedor: str | None, marca: str | None = None
) -> int:
    resultado = pontuar(consulta, titulo, marca)
    if (
        vendedor
        and not consulta.pede_acessorio
        and any(t in PALAVRAS_BRINQUEDO for t in termos_do_texto(vendedor))
    ):
        resultado = round(resultado * 0.3)
    return resultado


def pontuar_loja_brinquedos(consulta: Consulta, resultado: int) -> int:
    if consulta.pede_acessorio or not BUSCA_DE_BRINQUEDO.isdisjoint(consulta.termos):
        return resultado
    return round(resultado * 0.6)


def eh_titulo_de_acessorio(titulo: str) -> bool:
    return any(t in PALAVRAS_ACESSORIO for t in termos_do_texto(titulo)[:2])


def nucleo_da_busca(texto: str) -> str | None:
    """O que distingue a busca, sem o tipo genérico nem a finalidade.

    "estante para livros multy 4 prateleiras menta" vira "multy 4 prateleiras menta": a
    loja que lista o produto pelo nome da linha às vezes não o devolve na frase inteira.
    """
    palavras = corrigir(texto).split()
    mantidas: list[str] = []
    depois_de_para = False
    for palavra in palavras:
        termos = _termos_brutos(palavra)
        if depois_de_para:
            depois_de_para = False
            continue
        if termos and termos[0] in PALAVRAS_PARA:
            depois_de_para = True
            continue
        if all(
            t in PALAVRAS_VAZIAS or t in _produtos() or t in PALAVRAS_DE_INTENCAO for t in termos
        ):
            continue
        mantidas.append(palavra)
    distintiva = any(_distintiva(normalizar(p)) for p in mantidas)
    if len(mantidas) < 2 or len(mantidas) == len(palavras) or not distintiva:
        return None
    return " ".join(mantidas)


def _distintiva(palavra: str) -> bool:
    # nome de linha ou modelo pouco comum: fora do vocabulário dos títulos, sem ser cor,
    # número ou unidade
    return (
        len(palavra) >= 3
        and palavra.isalpha()
        and palavra not in _PALAVRAS_REAIS
        and palavra not in _VOCABULARIO
        and palavra not in CORES
        and palavra not in UNIDADES
        and _singular(palavra) not in _produtos()
    )
