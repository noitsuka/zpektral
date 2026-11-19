import hashlib
import json
import time
from typing import Any
from urllib.parse import urlsplit

from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.configuracao import Configuracoes
from app.dinheiro import para_centavos
from app.fontes.base import (
    ContextoBusca,
    Previa,
    cotar_pelo_navegador,
    escolher_para_cotar,
    montar_ofertas,
)
from app.modelos import Alerta, Loja, Oferta, Origem
from app.navegador.shopee import FreteShopeeNavegador, url_do_produto

API = "https://open-api.affiliate.shopee.com.br/graphql"
LIMITE = 50
# códigos de errors[].extensions.code na documentação da Open API de afiliados
LIMITE_EXCEDIDO = 10030
RECUSAS = {10020, LIMITE_EXCEDIDO, 10031, 10032, 10033, 10034, 10035}
# shortcut: o limite é de 2.000 consultas por hora sem dizer quando a janela vira; pausa fixa
# até a API informar o reinício
SEGUNDOS_PAUSA_LIMITE = 15 * 60
CONSULTA_GRAPHQL = (
    "{productOfferV2(keyword: %s, limit: %d, page: %d){nodes{itemId productName priceMin "
    "priceMax priceDiscountRate imageUrl shopName shopId offerLink productLink}"
    " pageInfo{page limit hasNextPage}}}"
)


def assinatura(id_app: str, instante: int, corpo: str, segredo: str) -> str:
    return hashlib.sha256(f"{id_app}{instante}{corpo}{segredo}".encode()).hexdigest()


def corpo_da_consulta(texto: str, pagina: int) -> str:
    return json.dumps(
        {"query": CONSULTA_GRAPHQL % (json.dumps(texto, ensure_ascii=False), LIMITE, pagina)},
        ensure_ascii=False,
        separators=(",", ":"),
    )


class FonteShopee:
    id = "shopee"
    nome = "Shopee"

    def __init__(
        self,
        http: ClienteHttp,
        config: Configuracoes,
        relogio=time.time,
        frete: FreteShopeeNavegador | None = None,
    ):
        self._http = http
        self._config = config
        self._relogio = relogio
        self._frete = frete
        self._ref = Loja(self.id, self.nome)
        self._pausa_ate = 0.0

    @property
    def ativa(self) -> bool:
        return bool(self._config.shopee_id_app and self._config.shopee_segredo.get_secret_value())

    async def _pagina(self, texto: str, pagina: int) -> tuple[list[dict[str, Any]], bool]:
        id_app, segredo = self._config.shopee_id_app, self._config.shopee_segredo.get_secret_value()
        corpo = corpo_da_consulta(texto, pagina)
        ts = int(self._relogio())
        autenticacao = (
            f"SHA256 Credential={id_app}, Timestamp={ts}, "
            f"Signature={assinatura(id_app, ts, corpo, segredo)}"
        )
        resposta = await self._http.requisitar(
            "POST",
            API,
            content=corpo.encode(),
            headers={"content-type": "application/json", "authorization": autenticacao},
        )
        dados = ler_json(resposta)
        if not isinstance(dados, dict):
            raise ErroExterno("shopee: resposta inesperada")
        if erros := dados.get("errors"):
            primeiro = erros[0] if isinstance(erros, list) and erros else {}
            primeiro = primeiro if isinstance(primeiro, dict) else {}
            extensoes = primeiro.get("extensions")
            codigo = extensoes.get("code") if isinstance(extensoes, dict) else None
            if codigo == LIMITE_EXCEDIDO:
                self._pausa_ate = self._relogio() + SEGUNDOS_PAUSA_LIMITE
            mensagem = str(primeiro.get("message") or "erro")[:200]
            raise ErroExterno(f"shopee: {mensagem}", bloqueio=codigo in RECUSAS)
        oferta = (dados.get("data") or {}).get("productOfferV2") or {}
        nos = oferta.get("nodes") or []
        continua = bool((oferta.get("pageInfo") or {}).get("hasNextPage"))
        return [n for n in nos if isinstance(n, dict)], continua

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        if self._relogio() < self._pausa_ate:
            raise ErroExterno("shopee: limite de consultas da hora atingido", bloqueio=True)
        inicio = time.monotonic()
        por_item: dict[Any, dict[str, Any]] = {}
        for pagina in range(1, self._config.shopee_paginas + 1):
            try:
                da_pagina, continua = await self._pagina(ctx.texto, pagina)
            except ErroExterno:
                # a pausa do limite já ficou marcada; o que as páginas anteriores trouxeram vale
                if not por_item:
                    raise
                break
            for no in da_pagina:
                por_item.setdefault(no.get("itemId"), no)
            if not continua or not da_pagina:
                break
        nos = list(por_item.values())
        lojas: dict[str, int | str] = {
            f"{self.id}:{n.get('itemId')}": loja
            for n in nos
            if isinstance(loja := n.get("shopId"), int | str) and loja
        }
        ofertas = montar_ofertas(self.id, nos, lambda no, p: self._oferta(no, p, ctx))
        if self._frete is None or ctx.endereco is None:
            return ofertas

        alvo = escolher_para_cotar(
            [o for o in ofertas if o.id in lojas],
            self._config.relevancia_minima_cotacao,
            self._config.navegador_cotacoes,
            lambda o: o,
        )
        if not alvo:
            return ofertas
        frete, cep = self._frete, ctx.endereco.cep
        produtos = [(o.id, lojas[o.id], o.id.split(":", 1)[1]) for o in alvo]
        orcamento = self._config.segundos_limite_fonte - (time.monotonic() - inicio) - 0.5
        return await cotar_pelo_navegador(
            ofertas,
            alvo,
            ctx,
            previa,
            orcamento,
            lambda destino: frete.cotar(produtos, cep, destino),
            lambda o: o.id,
        )

    def _oferta(self, no: dict[str, Any], posicao: int, ctx: ContextoBusca) -> Oferta | None:
        if not no.get("priceMin"):
            return None
        titulo = no.get("productName") or ""
        preco = para_centavos(no["priceMin"])
        # sem preço "de" na API: a porcentagem de desconto não vira preço antigo inventado
        alertas = []
        if no.get("priceMax") and para_centavos(no["priceMax"]) > preco:
            alertas.append(Alerta.PRECO_VARIA_POR_VERSAO)
        link = _da_shopee(no.get("offerLink")) or _da_shopee(no.get("productLink"))
        if not link and no.get("shopId") and no.get("itemId"):
            link = url_do_produto(no["shopId"], no["itemId"])
        return Oferta(
            id=f"{self.id}:{no.get('itemId')}",
            titulo=titulo,
            link=link or "",
            loja=self._ref,
            preco=preco,
            origem=Origem.MARKETPLACE,
            vendedor=no.get("shopName"),
            imagem=no.get("imageUrl"),
            frete=ctx.frete_sem_cotacao(),
            alertas=alertas,
            relevancia=ctx.relevancia_de(titulo, no.get("shopName")),
            posicao=posicao,
        )


def _da_shopee(link: object) -> str | None:
    """Só link https da própria Shopee: a resposta da API não escolhe para onde a pessoa vai."""
    if not isinstance(link, str):
        return None
    partes = urlsplit(link)
    host = partes.hostname or ""
    if partes.scheme == "https" and (host == "shopee.com.br" or host.endswith(".shopee.com.br")):
        return link
    return None
