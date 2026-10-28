import re
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

import orjson

from app.cache import CacheComValidade
from app.cliente_http import ClienteHttp, ErroExterno
from app.configuracao import Configuracoes
from app.dinheiro import para_centavos
from app.fontes.base import ContextoBusca, Previa, executar_no_prazo, montar_ofertas
from app.modelos import Loja, Oferta, Origem, Parcelamento
from app.relevancia import normalizar

SITE = "https://www.buscape.com.br"
PAGINAS_DE_PRODUTO = 8
TENTATIVAS_DE_BUSCA = 3
SEGUNDOS_CACHE_PRODUTO = 600
_NEXT_DATA = re.compile(rb'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class FonteBuscape:
    id = "buscape"
    nome = "Buscapé"

    def __init__(self, http: ClienteHttp, config: Configuracoes, lojas_diretas: Iterable[str] = ()):
        self._http = http
        self._config = config
        self._diretas = {_chave_lojista(nome) for nome in lojas_diretas}
        self._produtos: CacheComValidade[str, list[dict[str, Any]]] = CacheComValidade(
            SEGUNDOS_CACHE_PRODUTO, 2_000
        )

    @property
    def ativa(self) -> bool:
        return True

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        inicio = time.monotonic()
        resultados = [r for r in await self._resultados(ctx.texto) if _caminho(r)]
        vitrine = montar_ofertas(self.id, resultados, lambda r, p: self._da_vitrine(r, p, ctx))
        if previa is not None and vitrine:
            previa(vitrine)

        piso = self._config.relevancia_minima_cotacao
        detalhar = [
            (posicao, r, caminho)
            for posicao, r in enumerate(resultados)
            if (caminho := _caminho(r))
            and ctx.relevancia_de(_titulo(r)) >= piso
            and (r.get("storeCount") or 0) >= 2
        ][:PAGINAS_DE_PRODUTO]
        detalhadas: dict[int, list[Oferta]] = {}

        async def detalhar_produto(posicao: int, resultado: dict[str, Any], caminho: str) -> None:
            try:
                ofertas_da_pagina = await self._produtos.obter_ou_carregar(
                    caminho, lambda: self._ler_produto(caminho)
                )
            except ErroExterno:
                return
            detalhadas[posicao] = montar_ofertas(
                self.id,
                ofertas_da_pagina,
                lambda o, _: self._da_pagina(o, resultado, caminho, posicao, ctx),
            )

        orcamento = self._config.segundos_limite_fonte - (time.monotonic() - inicio) - 0.5
        await executar_no_prazo(orcamento, [detalhar_produto(*item) for item in detalhar])

        saida: list[Oferta] = []
        for posicao, resultado in enumerate(resultados):
            if detalhadas.get(posicao):
                saida.extend(detalhadas[posicao])
                continue
            saida.extend(o for o in vitrine if o.id == _id_vitrine(resultado))
        return saida

    async def _resultados(self, texto: str) -> list[dict[str, Any]]:
        palavras = texto.split()
        for tamanho in range(len(palavras), max(0, len(palavras) - TENTATIVAS_DE_BUSCA), -1):
            resposta = await self._http.requisitar(
                "GET", url_de_busca(" ".join(palavras[:tamanho])), aceitos=(200, 404)
            )
            if resposta.status_code == 200:
                return ler_resultados(resposta.content)
        return []

    async def _ler_produto(self, caminho: str) -> list[dict[str, Any]]:
        resposta = await self._http.requisitar("GET", SITE + caminho)
        return ler_ofertas_do_produto(resposta.content)

    def _da_vitrine(
        self, resultado: dict[str, Any], posicao: int, ctx: ContextoBusca
    ) -> Oferta | None:
        preco = resultado.get("price")
        lojista = (resultado.get("bestOffer") or {}).get("merchantName")
        if not preco or not isinstance(lojista, str) or not lojista or self._direta(lojista):
            return None
        titulo = _titulo(resultado)
        return Oferta(
            id=_id_vitrine(resultado),
            titulo=titulo,
            link=SITE + str(_caminho(resultado)),
            loja=self._loja(lojista),
            preco=para_centavos(preco),
            origem=Origem.COMPARADOR,
            vendedor=lojista,
            imagem=resultado.get("image"),
            frete=ctx.frete_sem_cotacao(),
            relevancia=ctx.relevancia_de(titulo),
            posicao=posicao,
        )

    def _da_pagina(
        self,
        oferta: dict[str, Any],
        resultado: dict[str, Any],
        caminho: str,
        posicao: int,
        ctx: ContextoBusca,
    ) -> Oferta | None:
        preco = oferta.get("price")
        lojista = oferta.get("sellerName")
        if not preco or not isinstance(lojista, str) or not lojista or self._direta(lojista):
            return None
        if oferta.get("stock") == 0:
            return None
        titulo = oferta.get("name") or _titulo(resultado)
        centavos = para_centavos(preco)
        return Oferta(
            id=f"{self.id}:{oferta.get('productID') or _id_vitrine(resultado)}:{oferta.get('id')}",
            titulo=titulo,
            link=SITE + caminho,
            loja=self._loja(lojista),
            preco=centavos,
            origem=Origem.COMPARADOR,
            vendedor=lojista,
            imagem=oferta.get("imageUrl") or resultado.get("image"),
            parcelamento=_parcelamento(oferta, centavos),
            frete=ctx.frete_sem_cotacao(),
            relevancia=ctx.relevancia_de(titulo),
            posicao=posicao,
        )

    def _direta(self, lojista: str) -> bool:
        return _chave_lojista(lojista) in self._diretas

    def _loja(self, lojista: str) -> Loja:
        return Loja(f"{self.id}:{_chave_lojista(lojista)}", lojista)


def url_de_busca(texto: str) -> str:
    termos = "+".join(quote(palavra, safe="") for palavra in texto.split())
    return f"{SITE}/busca/{termos}"


def _dados_da_pagina(html: bytes) -> dict[str, Any]:
    achado = _NEXT_DATA.search(html)
    if not achado:
        raise ErroExterno("www.buscape.com.br: página sem dados")
    try:
        dados = orjson.loads(achado.group(1))
    except orjson.JSONDecodeError:
        raise ErroExterno("www.buscape.com.br: dados ilegíveis") from None
    if not isinstance(dados, dict):
        raise ErroExterno("www.buscape.com.br: dados ilegíveis")
    estado = (dados.get("props") or {}).get("initialReduxState")
    return estado if isinstance(estado, dict) else {}


def ler_resultados(html: bytes) -> list[dict[str, Any]]:
    hits = (_dados_da_pagina(html).get("hits") or {}).get("hits") or []
    return [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []


def ler_ofertas_do_produto(html: bytes) -> list[dict[str, Any]]:
    ofertas = _dados_da_pagina(html).get("offers") or {}
    if not isinstance(ofertas, dict):
        return []
    unicas: dict[str, dict[str, Any]] = {}
    for lista in (ofertas.get("displayOffers"), ofertas.get("offerList")):
        for oferta in lista if isinstance(lista, list) else []:
            if isinstance(oferta, dict) and oferta.get("id") is not None:
                unicas.setdefault(str(oferta["id"]), oferta)
    return list(unicas.values())


def _parcelamento(oferta: dict[str, Any], centavos: int) -> Parcelamento | None:
    parcelas = oferta.get("numParcels")
    if not isinstance(parcelas, int) or parcelas < 2:
        return None
    valor = para_centavos(oferta.get("parcelValue") or 0)
    total = para_centavos(oferta.get("totalParceledValue") or 0)
    if valor <= 0 or total <= 0:
        return None
    total = max(total, centavos)
    return Parcelamento(parcelas=parcelas, valor=valor, total=total, juros=total > centavos)


def _caminho(resultado: dict[str, Any]) -> str | None:
    caminho = resultado.get("url")
    if not isinstance(caminho, str) or not caminho.startswith("/") or caminho.startswith("//"):
        return None
    return caminho


def _titulo(resultado: dict[str, Any]) -> str:
    return resultado.get("name") or resultado.get("shortName") or ""


def _id_vitrine(resultado: dict[str, Any]) -> str:
    return f"buscape:{resultado.get('objectId') or resultado.get('sourceId')}"


def _chave_lojista(nome: str) -> str:
    return normalizar(nome).replace(" ", "")
