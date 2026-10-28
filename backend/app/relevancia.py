import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.sinonimos import PALAVRAS_DE_PRODUTO, SINONIMOS, Sinonimo

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
_LETRA_DIGITO = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_MARCA_POLEGADA = re.compile(r"(\d)\s*(?:\"|\u201d|'')")

PALAVRAS_VAZIAS = frozenset(
    "a o as os de da do das dos e em no na nos nas com sem para por pra p um uma the".split()
)

PALAVRAS_ACESSORIO = frozenset(
    """
    capa capinha case pelicula protetor suporte cabo carregador adaptador fonte skin adesivo
    bolsa mochila maleta estojo base refil filtro peca borracha gaxeta prateleira gaveta
    puxador motoventilador termostato resistencia controle pulseira tampa painel rack
    acessorio cesto cuba botao copo jarra lamina helice mangueira valvula bico vedacao
    engrenagem correia parafuso rodizio limpa limpador fusivel lampada armario grelha
    amortecedor tapete assadeira pe pes
    """.split()
)

PALAVRAS_PARA = frozenset({"para", "pra", "p", "compativel", "compat"})
PARTE_DE = frozenset({"de", "da", "do", "das", "dos"})
COLETIVOS = frozenset({"jogo", "kit", "conjunto", "par", "combo", "caixa", "pacote", "linha"})
PALAVRAS_BRINQUEDO = frozenset(
    {"brinquedo", "toy", "infantil", "kid", "miniatura", "jr", "divertido", "divertida"}
)

UNIDADES = {"litro": "l", "lt": "l", "polegada": "pol", "volt": "v", "watt": "w"}
LETRAS_UNIDADE = frozenset("lvwkgx")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(car for car in texto if not unicodedata.combining(car))
    return _NAO_ALFANUMERICO.sub(" ", texto).strip()


def _singular(termo: str) -> str:
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
    for bruto in normalizar(_MARCA_POLEGADA.sub(r"\1 pol ", texto)).split():
        for peca in _separar_codigo(bruto):
            palavra = _singular(peca)
            saida.append(UNIDADES.get(palavra, palavra))
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


def _distancia(a: str, b: str) -> int:
    anterior2: list[int] = []
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            custo = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb))
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
    if len(chave) < 6:
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


def texto_para_lojas(texto: str) -> str:
    palavras = corrigir(texto).split()
    termos: list[str] = []
    dono: list[int] = []
    for i, palavra in enumerate(palavras):
        brutos = _termos_brutos(palavra)
        termos += brutos
        dono += [i] * len(brutos)
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


@dataclass(frozen=True, slots=True)
class Consulta:
    texto: str
    termos: tuple[str, ...]
    pesos: tuple[float, ...]
    pede_acessorio: bool

    @property
    def esta_vazia(self) -> bool:
        return not self.termos


@lru_cache(maxsize=1024)
def interpretar_consulta(texto: str) -> Consulta:
    corrigido = corrigir(texto)
    termos = tuple(dict.fromkeys(t for t in termos_do_texto(corrigido) if t not in PALAVRAS_VAZIAS))
    brutos = _termos_brutos(corrigido)
    palavras_do_produto = {
        s.termo: sum(t not in PALAVRAS_VAZIAS for t in brutos[inicio:fim])
        for inicio, fim, s in _sinonimos_em(brutos)
    }
    pesos = tuple(
        2.0 if _tem_numero(t) else float(max(1, palavras_do_produto.get(t, 1))) for t in termos
    )
    especiais = PALAVRAS_ACESSORIO | PALAVRAS_BRINQUEDO
    return Consulta(texto, termos, pesos, any(t in especiais for t in termos))


def _tem_numero(termo: str) -> bool:
    return any(c.isdigit() for c in termo)


def _acertos(consulta: Consulta, palavras_titulo: tuple[str, ...]) -> dict[str, int]:
    achados: dict[str, int] = {}
    posicoes: dict[str, int] = {}
    for i, t in enumerate(palavras_titulo):
        posicoes.setdefault(t, i)
    for termo in consulta.termos:
        if termo in posicoes:
            achados[termo] = posicoes[termo]
    for a, b in zip(consulta.termos, consulta.termos[1:], strict=False):
        par = a + b
        for i, t in enumerate(palavras_titulo):
            if t == par or (len(par) >= 6 and t.startswith(par)):
                achados.setdefault(a, i)
                achados.setdefault(b, i)
                break
    colado = "".join(palavras_titulo)
    for termo in consulta.termos:
        if termo in achados or len(termo) < 4:
            continue
        if termo in colado and not any(termo in t for t in palavras_titulo):
            achados[termo] = len(palavras_titulo)
    return achados


def pontuar(consulta: Consulta, titulo: str) -> int:
    if consulta.esta_vazia:
        return 100
    palavras_titulo = termos_do_texto(titulo)
    achados = _acertos(consulta, palavras_titulo)

    casado = 0.0
    total = sum(consulta.pesos)
    falta_numero = False
    palavras, palavras_achadas = 0, 0
    primeira_palavra = len(palavras_titulo)
    for termo, peso in zip(consulta.termos, consulta.pesos, strict=True):
        consumir = termo in achados
        numero = _tem_numero(termo)
        if not numero:
            palavras += 1
            palavras_achadas += consumir
            if consumir:
                primeira_palavra = min(primeira_palavra, achados[termo])
        if consumir:
            casado += peso
        elif numero:
            falta_numero = True

    resultado = casado / total * 95
    if falta_numero:
        resultado = min(resultado, 40)
    if palavras and not palavras_achadas:
        resultado = min(resultado, 15)

    if casado == total:
        frase = " ".join(t for t in palavras_titulo if t not in PALAVRAS_VAZIAS)
        if len(consulta.termos) == 1 or " ".join(consulta.termos) in frase:
            resultado += 5

    if (
        not consulta.pede_acessorio
        and casado
        and eh_secundario(palavras_titulo, primeira_palavra, consulta)
    ):
        resultado *= 0.3
    return round(resultado)


def eh_secundario(
    palavras_titulo: tuple[str, ...], primeiro_acerto: int, consulta: Consulta
) -> bool:
    inicio = palavras_titulo[:3]
    if any(t in PALAVRAS_ACESSORIO for t in inicio):
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
    return any(t in PALAVRAS_BRINQUEDO for t in palavras_titulo)


def pontuar_com_vendedor(consulta: Consulta, titulo: str, vendedor: str | None) -> int:
    resultado = pontuar(consulta, titulo)
    if (
        vendedor
        and not consulta.pede_acessorio
        and any(t in PALAVRAS_BRINQUEDO for t in termos_do_texto(vendedor))
    ):
        resultado = round(resultado * 0.3)
    return resultado


def pontuar_loja_brinquedos(consulta: Consulta, resultado: int) -> int:
    return resultado if consulta.pede_acessorio else round(resultado * 0.6)


def eh_titulo_de_acessorio(titulo: str) -> bool:
    return any(t in PALAVRAS_ACESSORIO for t in termos_do_texto(titulo)[:2])
