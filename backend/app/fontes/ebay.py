import asyncio
import base64
import time
from typing import Any
from urllib.parse import quote

from app.cambio import ServicoCambio
from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.configuracao import Configuracoes
from app.dinheiro import para_centavos
from app.fontes.base import ContextoBusca, Previa, montar_ofertas
from app.importacao import estimar_importacao
from app.modelos import Condicao, Frete, Loja, Oferta, Origem, StatusFrete

API = "https://api.ebay.com"
ESCOPO = "https://api.ebay.com/oauth/api_scope"
LIMITE = 50
MERCADO = "EBAY_US"
CONDICOES = {
    "new": Condicao.NOVO,
    "new other (see details)": Condicao.NOVO,
    "new with tags": Condicao.NOVO,
    "new with box": Condicao.NOVO,
    "new without tags": Condicao.NOVO,
    "certified - refurbished": Condicao.RECONDICIONADO,
    "excellent - refurbished": Condicao.RECONDICIONADO,
    "very good - refurbished": Condicao.RECONDICIONADO,
    "good - refurbished": Condicao.RECONDICIONADO,
    "seller refurbished": Condicao.RECONDICIONADO,
    "remanufactured": Condicao.RECONDICIONADO,
    "open box": Condicao.RECONDICIONADO,
}


def condicao_ebay(texto: object) -> Condicao | None:
    if not isinstance(texto, str) or not texto.strip():
        return None
    chave = texto.strip().lower()
    if chave in CONDICOES:
        return CONDICOES[chave]
    if "refurbished" in chave:
        return Condicao.RECONDICIONADO
    if "used" in chave or "pre-owned" in chave or "parts" in chave:
        return Condicao.USADO
    return None


def _dolares(valor: object) -> int | None:
    if not isinstance(valor, dict) or valor.get("currency") != "USD":
        return None
    centavos = para_centavos(str(valor.get("value")))
    return centavos if centavos >= 0 else None


def frete_para_o_brasil(item: dict[str, Any]) -> int | None:
    custos = []
    for opcao in item.get("shippingOptions") or []:
        if isinstance(opcao, dict) and (custo := _dolares(opcao.get("shippingCost"))) is not None:
            custos.append(custo)
    return min(custos) if custos else None


class FonteEbay:
    id = "ebay"
    nome = "eBay"

    def __init__(
        self, http: ClienteHttp, config: Configuracoes, cambio: ServicoCambio, relogio=time.time
    ):
        self._http = http
        self._config = config
        self._cambio = cambio
        self._relogio = relogio
        self._ref = Loja(self.id, self.nome)
        self._token: str | None = None
        self._expira = 0.0
        self._trava = asyncio.Lock()

    @property
    def ativa(self) -> bool:
        return bool(self._config.ebay_id_cliente and self._config.ebay_segredo.get_secret_value())

    async def _obter_token(self) -> str:
        if self._token and self._relogio() < self._expira:
            return self._token
        async with self._trava:
            if self._token and self._relogio() < self._expira:
                return self._token
            credencial = base64.b64encode(
                f"{self._config.ebay_id_cliente}:{self._config.ebay_segredo.get_secret_value()}".encode()
            ).decode()
            resposta = await self._http.requisitar(
                "POST",
                f"{API}/identity/v1/oauth2/token",
                tentativas=0,
                data={"grant_type": "client_credentials", "scope": ESCOPO},
                headers={"authorization": f"Basic {credencial}"},
            )
            corpo = ler_json(resposta)
            token = corpo.get("access_token") if isinstance(corpo, dict) else None
            if not isinstance(token, str) or not token:
                raise ErroExterno("ebay: resposta de token sem access_token")
            validade = corpo.get("expires_in")
            validade = validade if isinstance(validade, int) and validade > 0 else 7200
            self._token, self._expira = token, self._relogio() + max(60, validade - 300)
            return token

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        token, cotacao = await asyncio.gather(self._obter_token(), self._cambio.dolar())
        contexto = "country=BR" + (f",zip={ctx.endereco.cep}" if ctx.endereco else "")
        dados = await self._http.obter_json(
            f"{API}/buy/browse/v1/item_summary/search?q={quote(ctx.texto)}&limit={LIMITE}"
            "&filter=deliveryCountry:BR,buyingOptions:%7BFIXED_PRICE%7D",
            headers={
                "authorization": f"Bearer {token}",
                "x-ebay-c-marketplace-id": MERCADO,
                "x-ebay-c-enduserctx": f"contextualLocation={quote(contexto, safe='')}",
            },
        )
        if not isinstance(dados, dict):
            raise ErroExterno("ebay: resposta de busca inesperada")
        return montar_ofertas(
            self.id, dados.get("itemSummaries") or [], lambda i, p: self._oferta(i, p, ctx, cotacao)
        )

    def _oferta(
        self, item: dict[str, Any], posicao: int, ctx: ContextoBusca, cotacao: float
    ) -> Oferta | None:
        produto_usd = _dolares(item.get("price"))
        if not produto_usd:
            return None
        frete_usd = frete_para_o_brasil(item)
        preco, frete, importacao = estimar_importacao(
            produto_usd,
            frete_usd,
            cotacao,
            self._config.aliquota_imposto_importacao,
            self._config.aliquota_icms_importacao,
        )
        titulo = item.get("title") or ""
        vendedor = (item.get("seller") or {}).get("username")
        imagem = (item.get("image") or {}).get("imageUrl")
        return Oferta(
            id=f"{self.id}:{item.get('itemId')}",
            titulo=titulo,
            link=item.get("itemWebUrl") or "",
            loja=self._ref,
            preco=preco,
            origem=Origem.IMPORTADO,
            vendedor=vendedor,
            imagem=imagem,
            condicao=condicao_ebay(item.get("condition")),
            frete=Frete(StatusFrete.ESTIMADO, valor=frete)
            if frete is not None
            else Frete(StatusFrete.NAO_INFORMADO),
            importacao=importacao,
            relevancia=ctx.relevancia_de(titulo, vendedor),
            posicao=posicao,
        )
