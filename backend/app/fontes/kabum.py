import re
import time
from typing import Any
from urllib.parse import quote

from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.configuracao import Configuracoes
from app.dinheiro import ler_reais, para_centavos
from app.fontes.base import ContextoBusca, Previa, montar_ofertas
from app.modelos import (
    Condicao,
    Frete,
    Loja,
    Oferta,
    Origem,
    Parcelamento,
    StatusFrete,
)

API = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products"
SITE = "https://www.kabum.com.br"
TAMANHO_MAXIMO_PAGINA = 100
_PARCELA = re.compile(r"(\d+)\s*x\s*de\s*(R\$\s*[\d.,]+)", re.I)


class FonteKabum:
    id = "kabum"
    nome = "KaBuM!"

    def __init__(self, http: ClienteHttp, config: Configuracoes, relogio=time.time):
        self._http = http
        self._config = config
        self._relogio = relogio
        self._ref = Loja(self.id, self.nome)

    @property
    def ativa(self) -> bool:
        return True

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        tamanho = min(self._config.produtos_por_loja * 2, TAMANHO_MAXIMO_PAGINA)
        resposta = await self._http.requisitar(
            "GET",
            f"{API}?query={quote(ctx.texto)}&page_size={tamanho}&page_number=1",
            aceitos=(200, 404),
        )
        if resposta.status_code == 404:
            return []
        dados = ler_json(resposta)
        if not isinstance(dados, dict):
            raise ErroExterno("kabum: resposta de busca inesperada")
        agora = self._relogio()
        return montar_ofertas(
            self.id, dados.get("data") or [], lambda e, p: self._oferta(e, p, agora, ctx)
        )

    def _oferta(
        self, entrada: dict[str, Any], posicao: int, agora: float, ctx: ContextoBusca
    ) -> Oferta | None:
        a = entrada.get("attributes") or {}
        if not a.get("available") or not a.get("price"):
            return None

        cartao, pix = a["price"], a.get("price_with_discount") or a["price"]
        promocao = a.get("offer") or {}
        if promocao.get("price") and promocao.get("starts_at", 0) <= agora <= promocao.get(
            "ends_at", 0
        ):
            cartao, pix = (
                promocao["price"],
                promocao.get("price_with_discount") or promocao["price"],
            )

        id_produto = entrada.get("id")
        titulo = a.get("title") or ""
        vendedor = None
        if a.get("is_marketplace"):
            vendedor = (a.get("marketplace") or {}).get("seller_name")
        imagens = a.get("images") or (a.get("photos") or {}).get("g") or []
        slug = a.get("product_link") or ""
        antigo = a.get("old_price") or 0

        if a.get("has_free_shipping"):
            frete = Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0)
        else:
            frete = ctx.frete_sem_cotacao()

        return Oferta(
            id=f"{self.id}:{id_produto}",
            titulo=titulo,
            link=f"{SITE}/produto/{id_produto}/{slug}".rstrip("/"),
            loja=self._ref,
            preco=para_centavos(cartao),
            origem=Origem.MARKETPLACE if vendedor else Origem.LOJA,
            vendedor=vendedor or self.nome,
            imagem=imagens[0] if imagens else None,
            marca=(a.get("manufacturer") or {}).get("name"),
            preco_original=para_centavos(antigo) if antigo else None,
            preco_pix=para_centavos(pix),
            parcelamento=_parcelamento(a.get("max_installment"), para_centavos(cartao)),
            frete=frete,
            condicao=Condicao.RECONDICIONADO if a.get("is_openbox") else None,
            relevancia=ctx.relevancia_de(titulo, vendedor),
            posicao=posicao,
        )


def _parcelamento(texto: str | None, centavos_cartao: int) -> Parcelamento | None:
    if not texto:
        return None
    achado = _PARCELA.search(texto)
    if not achado:
        return None
    quantidade, valor = int(achado.group(1)), ler_reais(achado.group(2))
    total = quantidade * valor
    return Parcelamento(
        parcelas=quantidade,
        valor=valor,
        total=max(total, centavos_cartao),
        juros=total > centavos_cartao + quantidade,
    )
