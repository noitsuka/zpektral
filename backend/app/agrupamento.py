import math
import re
import statistics
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.modelos import Alerta, Oferta
from app.relevancia import eh_titulo_de_acessorio, normalizar

_MODELO = re.compile(r"(?<![a-z0-9-])(?=[a-z0-9-]*\d)(?=[a-z0-9-]*[a-z])[a-z0-9]+(?:-[a-z0-9]+)*")
_NAO_E_MODELO = re.compile(
    r"^(?:\d+(?:gb|tb|mb|mp|mah|w|v|hz|l|ml|kg|g|mm|cm|m|pol|btus?|rpm|x|k|p|fps|bits?|gen|"
    r"a|th|o|nd|rd|st)|[a-z]{1,3}\d{1,2}|(?:ddr|gddr|usb|hdmi|wifi|pcie|nvme|ps|rtx|gtx|rx|"
    r"i|ryzen|core|ultra|m)\d+[a-z]?|\d+x\d+|\d+[a-z]?)$"
)
_FORA_DO_CODIGO = re.compile(r"[^a-z0-9-]+")
_CAPACIDADE = re.compile(r"\b(\d+)\s*(gb|tb)\b")
_POLEGADAS = re.compile(r"\b(\d{2,3})\s*(?:\"|pol\b|polegadas\b|\u201d)")
_LITROS = re.compile(r"\b(\d{2,4})\s*(?:l|litros)\b")
_BTU = re.compile(r"\b(\d{4,5})\s*btus?\b")

RAZAO_FORA_DA_CURVA = 0.5


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


@dataclass(frozen=True, slots=True)
class Especificacoes:
    modelos: frozenset[str]
    capacidade: frozenset[str]
    polegadas: str | None
    litros: str | None
    btu: str | None
    voltagem: str | None

    @property
    def assinatura(self) -> str:
        partes = [
            *sorted(self.capacidade),
            self.polegadas,
            self.litros,
            self.btu,
            self.voltagem,
        ]
        return "/".join(p.lower() for p in partes if p)


def _texto_codigo(titulo: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo.casefold())
    texto = "".join(car for car in texto if not unicodedata.combining(car))
    return _FORA_DO_CODIGO.sub(" ", texto.replace(" - ", " "))


def especificacoes(oferta: Oferta) -> Especificacoes:
    return _especificacoes(oferta.titulo, oferta.voltagem)


@lru_cache(maxsize=65_536)
def _especificacoes(titulo: str, voltagem: str | None) -> Especificacoes:
    bruto = titulo.casefold()
    normalizado = normalizar(titulo)
    codigos = (m.replace("-", "") for m in _MODELO.findall(_texto_codigo(titulo)))
    modelos = frozenset(c for c in codigos if len(c) >= 5 and not _NAO_E_MODELO.match(c))
    if eh_titulo_de_acessorio(titulo):
        modelos = frozenset()
    polegadas = _POLEGADAS.search(bruto)
    litros = _LITROS.search(normalizado)
    btu = _BTU.search(normalizado)
    return Especificacoes(
        modelos=modelos,
        capacidade=frozenset(f"{n}{u}" for n, u in _CAPACIDADE.findall(normalizado)),
        polegadas=polegadas.group(1) if polegadas else None,
        litros=litros.group(1) if litros else None,
        btu=btu.group(1) if btu else None,
        voltagem=voltagem,
    )


def compativeis(a: Especificacoes, b: Especificacoes) -> bool:
    if a.capacidade and b.capacidade and a.capacidade != b.capacidade:
        return False
    pares = (
        (a.polegadas, b.polegadas),
        (a.litros, b.litros),
        (a.btu, b.btu),
        (a.voltagem, b.voltagem),
    )
    return all(not (x and y) or x == y for x, y in pares)


def _chaves_identidade(oferta: Oferta, especificacoes_oferta: Especificacoes) -> list[str]:
    chaves = [f"g:{oferta.ean}"] if oferta.ean else []
    assinatura = especificacoes_oferta.assinatura
    chaves.extend(
        f"g:{m}/{assinatura}" if assinatura else f"g:{m}"
        for m in sorted(especificacoes_oferta.modelos)
    )
    return chaves


def chave_propria(
    oferta: Oferta, especificacoes_oferta: Especificacoes | None = None
) -> str | None:
    chaves = _chaves_identidade(oferta, especificacoes_oferta or especificacoes(oferta))
    return chaves[0] if chaves else None


class _UniaoConjuntos:
    def __init__(self, n: int):
        self.pai = list(range(n))

    def raiz(self, i: int) -> int:
        while self.pai[i] != i:
            self.pai[i] = self.pai[self.pai[i]]
            i = self.pai[i]
        return i

    def unir(self, a: int, b: int) -> None:
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self.pai[max(ra, rb)] = min(ra, rb)


def atribuir_grupos(ofertas: list[Oferta]) -> None:
    uf = _UniaoConjuntos(len(ofertas))
    dono: dict[str, int] = {}
    chaves_de: list[list[str]] = []
    variantes: dict[str, dict[str, tuple[Especificacoes, int]]] = {}
    for i, o in enumerate(ofertas):
        s = especificacoes(o)
        chaves = _chaves_identidade(o, s)
        chaves_de.append(chaves)
        for chave in chaves:
            if chave in dono:
                uf.unir(dono[chave], i)
            else:
                dono[chave] = i
        for modelo in s.modelos:
            variantes.setdefault(modelo, {}).setdefault(s.assinatura, (s, i))

    for achados in variantes.values():
        if len(achados) < 2:
            continue
        entradas = list(achados.values())
        if all(
            compativeis(a, b) for n, (a, _) in enumerate(entradas) for b, _ in entradas[n + 1 :]
        ):
            primeira = entradas[0][1]
            for _, i in entradas[1:]:
                uf.unir(primeira, i)

    membros: dict[int, list[int]] = {}
    for i in range(len(ofertas)):
        membros.setdefault(uf.raiz(i), []).append(i)
    for indices in membros.values():
        chaves = [k for i in indices for k in chaves_de[i]]
        eans = [k for i in indices if ofertas[i].ean for k in chaves_de[i][:1]]
        chave = min(eans or chaves) if chaves else None
        for i in indices:
            ofertas[i].grupo = chave


def marcar_fora_da_curva(ofertas: list[Oferta]) -> None:
    membros: dict[str, list[Oferta]] = {}
    for o in ofertas:
        if o.grupo:
            membros.setdefault(o.grupo, []).append(o)
    for grupo_id in membros.values():
        if len({o.loja.id for o in grupo_id}) < 3:
            continue
        mediana = statistics.median(o.melhor_preco for o in grupo_id)
        for o in grupo_id:
            if o.melhor_preco < mediana * RAZAO_FORA_DA_CURVA:
                o.alertar(Alerta.PRECO_FORA_DA_CURVA)


MINIMO_OFERTAS_NIVEL = 10
RELEVANCIA_MINIMA_NIVEL = 90
RELEVANCIA_REBAIXADA = 50
FATOR_MINIMO_ABAIXO = 4
DESVIOS_ABAIXO = 3
MAD_PARA_DESVIO = 1.4826


def piso_de_preco(precos: list[int]) -> float | None:
    logs = [math.log(p) for p in precos if p > 0]
    if len(logs) < MINIMO_OFERTAS_NIVEL:
        return None
    centro = statistics.median(logs)
    mad = statistics.median(abs(v - centro) for v in logs)
    return centro - max(DESVIOS_ABAIXO * MAD_PARA_DESVIO * mad, math.log(FATOR_MINIMO_ABAIXO))


def rebaixar_muito_abaixo(ofertas: list[Oferta]) -> None:
    piso = piso_de_preco(
        [o.melhor_preco for o in ofertas if o.relevancia >= RELEVANCIA_MINIMA_NIVEL]
    )
    if piso is None:
        return
    for o in ofertas:
        if o.melhor_preco > 0 and math.log(o.melhor_preco) < piso:
            o.relevancia = min(o.relevancia, RELEVANCIA_REBAIXADA)
            o.alertar(Alerta.PRECO_FORA_DA_CURVA)
