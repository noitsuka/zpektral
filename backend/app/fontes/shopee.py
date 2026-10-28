import hashlib
import json
import time
from typing import Any

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
from app.modelos import Loja, Oferta, Origem
from app.navegador.shopee import FreteShopeeNavegador, url_do_produto

API = "https://open-api.affiliate.shopee.com.br/graphql"
LIMITE = 50
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
            mensagem = primeiro.get("message") if isinstance(primeiro, dict) else None
            raise ErroExterno(f"shopee: {str(mensagem or 'erro')[:200]}")
        oferta = (dados.get("data") or {}).get("productOfferV2") or {}
        nos = oferta.get("nodes") or []
        continua = bool((oferta.get("pageInfo") or {}).get("hasNextPage"))
        return [n for n in nos if isinstance(n, dict)], continua

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        inicio = time.monotonic()
        nos: list[dict[str, Any]] = []
        for pagina in range(1, self._config.shopee_paginas + 1):
            da_pagina, continua = await self._pagina(ctx.texto, pagina)
            nos.extend(da_pagina)
            if not continua or not da_pagina:
                break
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
        desconto = no.get("priceDiscountRate")
        original = None
        if isinstance(desconto, int | float) and 0 < desconto < 100:
            original = round(preco / (1 - desconto / 100))
        pagina = no.get("productLink")
        if not pagina and no.get("shopId") and no.get("itemId"):
            pagina = url_do_produto(no["shopId"], no["itemId"])
        return Oferta(
            id=f"{self.id}:{no.get('itemId')}",
            titulo=titulo,
            link=no.get("offerLink") or pagina or "",
            loja=self._ref,
            preco=preco,
            origem=Origem.MARKETPLACE,
            vendedor=no.get("shopName"),
            imagem=no.get("imageUrl"),
            preco_original=original,
            frete=ctx.frete_sem_cotacao(),
            relevancia=ctx.relevancia_de(titulo, no.get("shopName")),
            posicao=posicao,
        )
