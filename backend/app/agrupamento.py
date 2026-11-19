import math
import re
import statistics
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from itertools import product, starmap

from app.modelos import Alerta, Condicao, Oferta
from app.relevancia import (
    CORES,
    Consulta,
    abre_com_outro_tipo,
    consulta_pela_raridade,
    eh_titulo_de_acessorio,
    interpretar_consulta,
    normalizar,
    parcial_de_nome_raro,
    pontuar,
    termos_do_texto,
)

_MODELO = re.compile(r"(?<![a-z0-9-])(?=[a-z0-9-]*\d)(?=[a-z0-9-]*[a-z])[a-z0-9]+(?:-[a-z0-9]+)*")
_NAO_E_MODELO = re.compile(
    r"^(?:\d+(?:gb|tb|mb|mp|mah|w|v|hz|l|ml|kg|g|mm|cm|m|pol|btus?|rpm|x|k|p|fps|bits?|gen|"
    r"a|th|o|nd|rd|st)|[a-z]{1,3}\d{1,2}|(?:ddr|gddr|usb|hdmi|wifi|pcie|nvme|ps|rtx|gtx|rx|"
    r"i|ryzen|core|ultra|m)\d+[a-z]?|\d+(?:x\d+)+|\d+[a-z]?)$"
)
_FORA_DO_CODIGO = re.compile(r"[^a-z0-9-]+")
_CAPACIDADE = re.compile(r"\b(\d+)\s*(gb|tb)\b")
_POLEGADAS = re.compile(r"\b(\d{2,3})\s*(?:\"|pol\b|polegadas\b|\u201d)")
_LITROS = re.compile(r"\b(\d{2,4})\s*(?:l|litros)\b")
_BTU = re.compile(r"\b(\d{4,5})\s*btus?\b")
_MOVEL = re.compile(r"\b(\d+) (prateleira|porta|gaveta)\b")
# "Kit 5 peças" é um jogo, não cinco unidades do produto.
_UNIDADES = re.compile(
    r"\b(?:kit|pack|pacote|combo|caixa|leve)(?: com| c| de)? (\d+)\b(?! peca)"
    r"|\b(\d+) (?:unidade|und|un)\b"
    r"|\b(\d+) ?x\b"
)
# "com 16 pilhas" contra "com 2 pilhas": a contagem do mesmo item separa pacotes
_CONTAGEM = re.compile(r"\b(\d+) ([a-z]{3,}s)\b")
# o que se vende em quantidade: "4 pilhas" é pacote, mesmo sem a palavra kit
_EMBALAGENS = frozenset(
    "pilhas rolos latas garrafas capsulas saches fraldas sabonetes refis unidades".split()
)
_PACOTE_SEM_NUMERO = frozenset({"cartela", "blister", "fardo"})

RAZAO_FORA_DA_CURVA = 0.5


@dataclass(frozen=True, slots=True)
class Especificacoes:
    modelos: frozenset[str]
    assinatura: str
    cores: frozenset[str]
    marca: str | None
    ean: str | None
    # (atributo, valor) de tudo que separa variantes e foi encontrado na oferta.
    criticos: frozenset[tuple[str, str | None]]
    atributos: frozenset[str]


def _texto_codigo(titulo: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo.casefold())
    texto = "".join(car for car in texto if not unicodedata.combining(car))
    return _FORA_DO_CODIGO.sub(" ", texto.replace(" - ", " "))


def especificacoes(oferta: Oferta) -> Especificacoes:
    return _especificacoes(
        oferta.titulo, oferta.voltagem, oferta.condicao, oferta.marca, oferta.ean
    )


@lru_cache(maxsize=65_536)
def _especificacoes(
    titulo: str,
    voltagem: str | None,
    condicao: Condicao | None,
    marca: str | None,
    ean: str | None,
) -> Especificacoes:
    bruto = titulo.casefold()
    normalizado = normalizar(titulo)
    termos = termos_do_texto(titulo)
    texto = " ".join(termos)
    codigos = (m.replace("-", "") for m in _MODELO.findall(_texto_codigo(titulo)))
    modelos = frozenset(c for c in codigos if len(c) >= 5 and not _NAO_E_MODELO.match(c))
    if eh_titulo_de_acessorio(titulo):
        modelos = frozenset()
    capacidade = sorted({f"{n}{u}" for n, u in _CAPACIDADE.findall(normalizado)})
    polegadas = _POLEGADAS.search(bruto)
    litros = _LITROS.search(normalizado)
    btu = _BTU.search(normalizado)
    medidas = {
        "polegadas": polegadas.group(1) if polegadas else None,
        "litros": litros.group(1) if litros else None,
        "btu": btu.group(1) if btu else None,
        "voltagem": voltagem,
    }
    moveis = {peca: f"{n}{peca}s" for n, peca in reversed(_MOVEL.findall(texto))}
    kit = _UNIDADES.search(texto)
    unidades = int(kit.group(1) or kit.group(2) or kit.group(3)) if kit else 1
    marca = next(iter(normalizar(marca).split()), None) if marca else None
    contagens = {f"qtd_{nome}": n for n, nome in _CONTAGEM.findall(normalizado)}
    valores = {
        "capacidade": "/".join(capacidade),
        **medidas,
        **moveis,
        **contagens,
        "marca": marca,
        "ean": ean,
    }
    criticos = {(nome, valor) for nome, valor in valores.items() if valor}
    # Título sem kit é unidade avulsa e sem condição é novo: a ausência também é um valor.
    if unidades == 1:
        unidades = max(
            (int(n) for n, nome in _CONTAGEM.findall(normalizado) if nome in _EMBALAGENS),
            default=1,
        )
    if "combo" in termos:
        pacote = "combo"
    elif unidades > 1:
        pacote = f"kit{unidades}"
    elif _PACOTE_SEM_NUMERO & set(termos):
        pacote = "pacote"
    else:
        pacote = None
    criticos.add(("unidades", pacote))
    criticos.add(("condicao", None if condicao in (None, Condicao.NOVO) else str(condicao)))
    return Especificacoes(
        modelos=modelos,
        assinatura="/".join(p.lower() for p in [*capacidade, *medidas.values()] if p),
        cores=CORES.intersection(termos),
        marca=marca,
        ean=ean,
        criticos=frozenset(criticos),
        atributos=frozenset(nome for nome, _ in criticos),
    )


def compativeis(a: Especificacoes, b: Especificacoes) -> bool:
    if a.cores and b.cores and not a.cores & b.cores:
        return False
    divergentes = len(a.atributos & b.atributos) - len(a.criticos & b.criticos)
    if divergentes == 1 and a.ean and a.ean == b.ean:
        # A marca vem do cadastro da loja ("LG", "Genérico") e não separa quem tem o mesmo EAN.
        return bool(a.marca and b.marca and a.marca != b.marca)
    return not divergentes


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
    perfil = especificacoes_oferta or especificacoes(oferta)
    chaves = _chaves_identidade(oferta, perfil)
    if not chaves:
        return None
    if oferta.ean:
        return chaves[0]
    # grupo provisório, antes do agrupamento final: código de modelo sozinho junta
    # cores e marcas diferentes, então a chave leva os dois
    extras = [perfil.marca or "", *sorted(perfil.cores)]
    return "/".join([chaves[0], *extras]).rstrip("/")


class _UniaoConjuntos:
    def __init__(self, perfis: list[Especificacoes]):
        self.pai = list(range(len(perfis)))
        self.perfis = [{p} for p in perfis]

    def raiz(self, i: int) -> int:
        while self.pai[i] != i:
            self.pai[i] = self.pai[self.pai[i]]
            i = self.pai[i]
        return i

    def unir(self, a: int, b: int) -> None:
        ra, rb = self.raiz(a), self.raiz(b)
        if ra == rb or not all(starmap(compativeis, product(self.perfis[ra], self.perfis[rb]))):
            return
        menor, maior = min(ra, rb), max(ra, rb)
        self.pai[maior] = menor
        self.perfis[menor] |= self.perfis[maior]


def _juntar_variantes(
    uf: _UniaoConjuntos, perfis_ofertas: list[Especificacoes], variantes: list[list[int]]
) -> None:
    for indices in variantes:
        for i in indices[1:]:
            uf.unir(indices[0], i)
    if len(variantes) < 2:
        return
    primeiras = [indices[0] for indices in variantes]
    perfis = [perfis_ofertas[i] for i in primeiras]
    vizinhos = [{n} for n in range(len(perfis))]
    for n, a in enumerate(perfis):
        for m in range(n + 1, len(perfis)):
            b = perfis[m]
            # EANs diferentes nunca casam; o teste direto poupa a chamada no caso mais comum.
            if not (a.ean and b.ean and a.ean != b.ean) and compativeis(a, b):
                vizinhos[n].add(m)
                vizinhos[m].add(n)
    # Só entra quem casa com um único conjunto coerente: o título sem cor que serve
    # tanto para o preto quanto para o branco fica sozinho em vez de escolher um.
    claras = [all(viz <= vizinhos[m] for m in viz) for viz in vizinhos]
    for n, viz in enumerate(vizinhos):
        if claras[n]:
            for m in viz:
                if m > n and claras[m]:
                    uf.unir(primeiras[n], primeiras[m])


def _rotulo(perfis: set[Especificacoes]) -> str:
    partes = {v for s in perfis for nome, v in s.criticos if v and nome != "ean"}
    partes.update(*(s.cores for s in perfis))
    return "/".join(sorted(partes)).lower()


@lru_cache(maxsize=65_536)
def _palavras(titulo: str) -> tuple[str, ...]:
    return tuple(normalizar(titulo).split())


def _marca_no_titulo(titulo: str, conhecidas: frozenset[str]) -> str | None:
    if not conhecidas:
        return None
    return next((t for t in _palavras(titulo) if t in conhecidas), None)


def atribuir_grupos(ofertas: list[Oferta]) -> None:
    # quem não informa a marca (marketplaces) recebe a que outra loja informou e está no título
    conhecidas = frozenset(
        normalizar(o.marca).split()[0] for o in ofertas if o.marca and normalizar(o.marca)
    ) - {"generico", "generica"}
    perfis = [
        especificacoes(o)
        if o.marca
        else _especificacoes(
            o.titulo, o.voltagem, o.condicao, _marca_no_titulo(o.titulo, conhecidas), o.ean
        )
        for o in ofertas
    ]
    uf = _UniaoConjuntos(perfis)
    por_ean: dict[str, dict[tuple, list[int]]] = {}
    por_modelo: dict[str, dict[tuple, list[int]]] = {}
    chaves_de = [_chaves_identidade(o, s) for o, s in zip(ofertas, perfis, strict=True)]
    for i in sorted(range(len(ofertas)), key=lambda i: ofertas[i].id):
        s = perfis[i]
        # Só os atributos críticos e as cores decidem a compatibilidade.
        variante = (s.criticos, s.cores)
        if s.ean:
            por_ean.setdefault(s.ean, {}).setdefault(variante, []).append(i)
        for modelo in s.modelos:
            por_modelo.setdefault(modelo, {}).setdefault(variante, []).append(i)
    # O EAN vem primeiro: quando o código de modelo puxa para outro lado, vale o EAN.
    for baldes in (por_ean, por_modelo):
        for chave in sorted(baldes):
            _juntar_variantes(uf, perfis, list(baldes[chave].values()))

    membros: dict[int, list[int]] = {}
    for i in range(len(ofertas)):
        membros.setdefault(uf.raiz(i), []).append(i)
    por_chave: dict[str, list[int]] = {}
    for raiz, indices in membros.items():
        chaves = [k for i in indices for k in chaves_de[i]]
        eans = [chaves_de[i][0] for i in indices if perfis[i].ean]
        if chaves:
            por_chave.setdefault(min(eans or chaves), []).append(raiz)
        else:
            for i in indices:
                ofertas[i].grupo = None
    for chave, raizes in por_chave.items():
        # O grupo maior mantém a chave de sempre (o histórico usa ela); os outros que
        # dividem a mesma chave levam no fim o que os diferencia.
        rotulos = {r: _rotulo(uf.perfis[r]) for r in raizes} if len(raizes) > 1 else {}
        raizes.sort(key=lambda r: (-len(membros[r]), rotulos.get(r, "")))
        for n, raiz in enumerate(raizes):
            grupo = f"{chave}/{rotulos[raiz]}" if n else chave
            for i in membros[raiz]:
                ofertas[i].grupo = grupo


def marcar_fora_da_curva(ofertas: list[Oferta]) -> None:
    membros: dict[str, list[Oferta]] = {}
    for o in ofertas:
        if o.grupo:
            membros.setdefault(o.grupo, []).append(o)
    for do_grupo in membros.values():
        # o preço da versão mais barata não é o do produto: não entra na mediana
        referencia = [o for o in do_grupo if Alerta.PRECO_VARIA_POR_VERSAO not in o.alertas]
        if len({o.loja.id for o in referencia}) < 3:
            continue
        mediana = statistics.median(o.melhor_preco for o in referencia)
        for o in do_grupo:
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


RELEVANCIA_PARECIDA = 70  # o site esconde abaixo disso
RELEVANCIA_PARCIAL = 45
LOJAS_COM_O_PEDIDO = 3
CASA_O_RESTO = 90  # nota de quem traz todas as palavras que sobraram


def soltar_palavras_sem_eco(ofertas: list[Oferta], consulta: Consulta) -> set[str]:
    """Palavra da busca que nenhuma oferta de nenhuma loja traz deixa de contar na nota.

    Ela não separa uma oferta da outra e escondia todas: em "air fryer bonita", nenhum anúncio
    diz "bonita", e toda air fryer ficava com 63. A oferta continua com a palavra entre as que
    faltaram, e o site a mostra como parecida. Número não sai: a capacidade pedida que nenhuma
    loja tem não vira outra capacidade. Devolve os ids das ofertas que passaram a aparecer.
    """
    vistos: set[str] = set()
    for o in ofertas:
        vistos.update(termos_do_texto(o.titulo))
        if o.marca:
            vistos.update(termos_do_texto(o.marca))
    sem_eco = {t for t in consulta.termos if t not in vistos and t.isalpha()}
    if not sem_eco or consulta.gtin:
        return set()
    texto = " ".join(p for p, termos in consulta.palavras if not termos or set(termos) - sem_eco)
    reduzida = interpretar_consulta(texto)
    if reduzida.esta_vazia:
        return set()
    promovidas = set()
    for o in ofertas:
        if o.relevancia >= RELEVANCIA_PARECIDA or Alerta.PRECO_FORA_DA_CURVA in o.alertas:
            continue
        # só sobe quem traz todas as outras palavras: em "tenis de corida masculino 42", sem o
        # erro que nenhum anúncio repete, o relógio masculino de 42 mm continua fora
        if pontuar(reduzida, o.titulo, o.marca) < CASA_O_RESTO:
            continue
        if (nova := round(_reavaliada(o, consulta, reduzida))) >= RELEVANCIA_PARECIDA:
            o.relevancia = min(100, nova)
            promovidas.add(o.id)
    return promovidas


def mostrar_parciais(ofertas: list[Oferta], consulta: Consulta) -> set[str]:
    """Com menos de três lojas vendendo o que foi pedido, reavalia a busca pelo peso da
    raridade e mostra como parecidas as ofertas que passam, com o que faltou indicado no site.

    Em "mangá punpun", os volumes de Boa Noite Punpun, que não repetem "mangá", entram; a
    camiseta de manga curta não. Também entra o que só não traz um nome raro, que a loja
    escreve de outro jeito: em "oyasumi punpun", a edição brasileira. Fica de fora o título que
    abre com outro tipo de produto, como a caneca, e as travas da relevância (outra cor, outra
    capacidade, outra marca, peça) seguem valendo. Devolve os ids das ofertas que passaram a
    aparecer.
    """
    lojas = {o.loja.id for o in ofertas if o.relevancia >= RELEVANCIA_PARECIDA}
    if len(lojas) >= LOJAS_COM_O_PEDIDO:
        return set()
    rara = consulta_pela_raridade(consulta.texto)
    promovidas = set()
    for o in ofertas:
        if (
            o.relevancia >= RELEVANCIA_PARECIDA
            or Alerta.PRECO_FORA_DA_CURVA in o.alertas
            or abre_com_outro_tipo(consulta, o.titulo)
        ):
            continue
        nota = _reavaliada(o, consulta, rara)
        if nota >= RELEVANCIA_PARECIDA or (
            nota >= RELEVANCIA_PARCIAL
            and parcial_de_nome_raro(consulta, o.titulo, o.termos_ausentes)
        ):
            o.relevancia = RELEVANCIA_PARECIDA
            promovidas.add(o.id)
    return promovidas


def _reavaliada(o: Oferta, consulta: Consulta, outra: Consulta) -> float:
    # a nota da loja já traz os descontos de vendedor e de loja de brinquedos: a proporção
    # entre as duas contas os mantém
    cheia = pontuar(consulta, o.titulo, o.marca)
    return o.relevancia * pontuar(outra, o.titulo, o.marca) / cheia if cheia else 0.0


def rebaixar_muito_abaixo(ofertas: list[Oferta]) -> None:
    piso = piso_de_preco(
        [
            o.melhor_preco
            for o in ofertas
            if o.relevancia >= RELEVANCIA_MINIMA_NIVEL
            and Alerta.PRECO_VARIA_POR_VERSAO not in o.alertas
        ]
    )
    if piso is None:
        return
    for o in ofertas:
        if o.melhor_preco > 0 and math.log(o.melhor_preco) < piso:
            o.relevancia = min(o.relevancia, RELEVANCIA_REBAIXADA)
            o.alertar(Alerta.PRECO_FORA_DA_CURVA)
