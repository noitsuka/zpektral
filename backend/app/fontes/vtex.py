import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib import resources
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from app.cache import CacheComValidade
from app.cliente_http import ClienteHttp, ErroExterno
from app.configuracao import Configuracoes
from app.dinheiro import para_centavos
from app.fontes.base import (
    ContextoBusca,
    Previa,
    entrega_mais_barata,
    escolher_para_cotar,
    executar_no_prazo,
    ler_prazo,
)
from app.modelos import (
    Alerta,
    Frete,
    Loja,
    Oferta,
    OpcaoFrete,
    Origem,
    Parcelamento,
    StatusFrete,
)
from app.relevancia import normalizar, pontuar_loja_brinquedos

log = logging.getLogger("zpektral.vtex")

JANELA_MAXIMA_LEGADA = 50
VENDEDOR_PROPRIO = "1"
GRUPO_CARTAO = "creditCardPaymentGroup"
DESVIO_DE_PRECO = 0.2
_ID_INTERNO = re.compile(r"\s*\([^)]*\)\s*$")
VENDEDORES_INSTAVEIS_MAXIMO = 10_000


@dataclass(frozen=True, slots=True)
class LojaVtex:
    id: str
    nome: str
    dominio: str
    busca: str = "auto"
    sc: int | None = None
    segmento: str = "geral"
    instavel: bool = False


def titulo_do_item(nome_produto: str, item: dict[str, Any]) -> str:
    nome = (item.get("name") or "").strip()
    if not nome_produto:
        return nome or item.get("nameComplete") or ""
    if not nome or normalizar(nome) in normalizar(nome_produto):
        return nome_produto
    if normalizar(nome_produto) in normalizar(nome):
        return nome
    return f"{nome_produto} {nome}" if len(nome) <= 40 else nome_produto


def carregar_lojas() -> list[LojaVtex]:
    bruto = resources.files("app").joinpath("dados/lojas_vtex.json").read_text("utf-8")
    return [LojaVtex(**entrada) for entrada in json.loads(bruto)]


@dataclass(slots=True)
class _Candidata:
    oferta: Oferta
    sku: str
    vendedor: str
    cotada: bool = False


class FonteVtex:
    def __init__(
        self,
        loja: LojaVtex,
        http: ClienteHttp,
        config: Configuracoes,
        cotacoes: "CacheComValidade[tuple[str, str, str, str], Cotacao] | None" = None,
    ):
        self._cotacoes = (
            cotacoes
            if cotacoes is not None
            else CacheComValidade(config.segundos_cache_cotacao, 1000)
        )
        self.id = loja.id
        self.nome = loja.nome
        self._loja = loja
        self._http = http
        self._config = config
        self._base = f"https://{loja.dominio}"
        self._ref = Loja(loja.id, loja.nome)
        self._instavel = loja.instavel
        self._vendedores_instaveis: set[str] = set()
        self._auditorias = 0

    @property
    def ativa(self) -> bool:
        return True

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        inicio = time.monotonic()
        produtos = await self._produtos(ctx.texto)
        candidatas = self._candidatas(produtos, ctx)

        a_cotar = escolher_para_cotar(
            candidatas,
            self._config.relevancia_minima_cotacao,
            self._config.cotacoes_por_loja,
            lambda c: c.oferta,
        )

        if previa is not None and a_cotar:
            for c in candidatas:
                c.oferta.frete = ctx.frete_calculando() if c in a_cotar else ctx.frete_sem_cotacao()
                c.oferta.consolidar()
            previa([c.oferta for c in candidatas])

        orcamento = self._config.segundos_limite_fonte - (time.monotonic() - inicio) - 0.5
        await executar_no_prazo(orcamento, [self._cotar(c, ctx) for c in a_cotar])

        for c in candidatas:
            if not c.cotada:
                c.oferta.frete = ctx.frete_sem_cotacao()
        return [c.oferta.consolidar() for c in candidatas]

    async def _produtos(self, texto: str) -> list[dict[str, Any]]:
        modo = self._loja.busca
        if modo == "legacy":
            return await self._busca_legada(texto)
        try:
            produtos = await self._busca_inteligente(texto)
        except ErroExterno:
            if modo == "is":
                raise
            return await self._busca_legada(texto)
        if not produtos and modo == "auto":
            return await self._busca_legada(texto)
        return produtos

    async def _busca_inteligente(self, texto: str) -> list[dict[str, Any]]:
        url = (
            f"{self._base}/api/io/_v/api/intelligent-search/product_search/"
            f"?query={quote(texto)}&count={self._config.produtos_por_loja}"
            "&page=1&locale=pt-BR&hideUnavailableItems=true"
        )
        dados = await self._http.obter_json(url)
        produtos = dados.get("products") if isinstance(dados, dict) else None
        return produtos if isinstance(produtos, list) else []

    async def _busca_legada(self, texto: str) -> list[dict[str, Any]]:
        ultimo = min(self._config.produtos_por_loja, JANELA_MAXIMA_LEGADA) - 1
        url = (
            f"{self._base}/api/catalog_system/pub/products/search"
            f"?ft={quote(texto)}&_from=0&_to={ultimo}"
        )
        dados = await self._http.obter_json(url, aceitos=(200, 206))
        return dados if isinstance(dados, list) else []

    def _candidatas(self, produtos: list[dict[str, Any]], ctx: ContextoBusca) -> list[_Candidata]:
        saida: list[_Candidata] = []
        for posicao, produto in enumerate(produtos):
            link = self._montar_link(produto)
            vistos: set[tuple[str, int]] = set()
            for item in produto.get("items") or []:
                titulo = titulo_do_item(produto.get("productName") or "", item)
                imagens = item.get("images") or []
                for vendedor in item.get("sellers") or []:
                    try:
                        oferta_comercial = vendedor.get("commertialOffer") or {}
                        preco = oferta_comercial.get("Price")
                        if not preco or not oferta_comercial.get("AvailableQuantity"):
                            continue
                        centavos = para_centavos(preco)
                        id_vendedor = str(vendedor.get("sellerId"))
                        if (id_vendedor, centavos) in vistos:
                            continue
                        vistos.add((id_vendedor, centavos))
                        pix, parcelamentos = _pagamento_catalogo(
                            oferta_comercial.get("Installments") or []
                        )
                        sku = str(item.get("itemId"))
                        oferta = Oferta(
                            id=f"{self.id}:{sku}:{id_vendedor}",
                            titulo=titulo,
                            link=_com_sku(link, sku),
                            link_carrinho=self._link_carrinho(sku, id_vendedor),
                            loja=self._ref,
                            preco=centavos,
                            origem=Origem.LOJA
                            if id_vendedor == VENDEDOR_PROPRIO
                            else Origem.MARKETPLACE,
                            vendedor=vendedor.get("sellerName"),
                            imagem=imagens[0].get("imageUrl") if imagens else None,
                            marca=produto.get("brand"),
                            ean=item.get("ean") or None,
                            preco_original=para_centavos(oferta_comercial["ListPrice"])
                            if oferta_comercial.get("ListPrice")
                            else None,
                            preco_pix=pix,
                            parcelamento=parcelamentos,
                            relevancia=self._relevancia(ctx, titulo, vendedor.get("sellerName")),
                            posicao=posicao,
                        )
                        saida.append(_Candidata(oferta, str(item.get("itemId")), id_vendedor))
                    except (ValueError, TypeError, AttributeError, KeyError) as excecao:
                        log.info("%s: oferta malformada ignorada (%r)", self.id, excecao)
        return saida

    def _relevancia(self, ctx: ContextoBusca, titulo: str, vendedor: str | None) -> int:
        resultado = ctx.relevancia_de(titulo, vendedor)
        if self._loja.segmento == "brinquedos":
            resultado = pontuar_loja_brinquedos(ctx.consulta, resultado)
        return resultado

    def _link_carrinho(self, sku: str, vendedor: str) -> str:
        parametros = urlencode(
            {"sku": sku, "qty": 1, "seller": vendedor, "sc": self._loja.sc or 1, "redirect": "true"}
        )
        return f"{self._base}/checkout/cart/add?{parametros}"

    def _montar_link(self, produto: dict[str, Any]) -> str:
        link = produto.get("link") or ""
        if link.startswith("http://"):
            return "https://" + link[len("http://") :]
        if link.startswith("https://"):
            return link
        if link.startswith("/"):
            return self._base + link
        return f"{self._base}/{produto.get('linkText', '')}/p"

    async def _cotar(self, candidata: _Candidata, ctx: ContextoBusca) -> None:
        corpo: dict[str, Any] = {
            "items": [{"id": candidata.sku, "quantity": 1, "seller": candidata.vendedor}],
            "country": "BRA",
        }
        if ctx.endereco is not None:
            corpo["postalCode"] = ctx.endereco.cep
        url = f"{self._base}/api/checkout/pub/orderForms/simulation"
        if self._loja.sc is not None:
            url += f"?sc={self._loja.sc}"

        instavel = self._instavel or candidata.vendedor in self._vendedores_instaveis
        auditar = (
            instavel
            or self._auditorias < self._config.aquecimento_auditoria_cotacao
            or random.random() < self._config.taxa_auditoria_cotacao
        )
        if auditar:
            self._auditorias += 1

        async def simular() -> Cotacao:
            if not auditar:
                return Cotacao(compactar(await self._http.enviar_json(url, corpo)), time.time())
            primeira, segunda = await asyncio.gather(
                self._http.enviar_json(url, corpo), self._http.enviar_json(url, corpo)
            )
            return Cotacao(compactar(primeira), time.time(), compactar(segunda))

        chave = (self._loja.dominio, candidata.sku, candidata.vendedor, corpo.get("postalCode", ""))
        try:
            cotacao = await self._cotacoes.obter_ou_carregar(chave, simular)
        except ErroExterno:
            return
        tem_cep = ctx.endereco is not None
        dados = cotacao.dados
        if cotacao.segunda_resposta is not None:
            dados, estavel = _conservadora(
                candidata.oferta, cotacao.dados, cotacao.segunda_resposta, tem_cep
            )
            if not estavel and not instavel:
                log.warning(
                    "checkout de %s respondeu valores diferentes para o vendedor %s",
                    self.id,
                    candidata.vendedor,
                )
                if len(self._vendedores_instaveis) < VENDEDORES_INSTAVEIS_MAXIMO:
                    self._vendedores_instaveis.add(candidata.vendedor)
                instavel = True
        if instavel:
            candidata.oferta.alertar(Alerta.PRECO_INSTAVEL)
        aplicar_simulacao(candidata.oferta, dados, tem_cep=tem_cep, cotada_em=cotacao.obtida_em)
        candidata.oferta.consolidar()
        candidata.cotada = True


@dataclass(frozen=True, slots=True)
class Cotacao:
    dados: dict[str, Any]
    obtida_em: float
    segunda_resposta: dict[str, Any] | None = None


_CAMPOS_ITEM = ("price", "listPrice", "sellingPrice", "availability")
_CAMPOS_SLA = (
    "id",
    "name",
    "deliveryChannel",
    "price",
    "tax",
    "shippingEstimate",
    "shippingEstimateDate",
    "deliveryIds",
    "pickupDistance",
    "pickupStoreInfo",
)


def compactar(dados: dict[str, Any]) -> dict[str, Any]:
    itens = dados.get("items") or []
    logistica = dados.get("logisticsInfo") or []
    opcoes = (dados.get("paymentData") or {}).get("installmentOptions") or []
    return {
        "items": [{k: itens[0].get(k) for k in _CAMPOS_ITEM}] if itens else [],
        "totals": [t for t in dados.get("totals") or [] if t.get("id") == "Tax"],
        "logisticsInfo": [
            {
                "slas": [
                    {
                        **{k: s.get(k) for k in _CAMPOS_SLA if k != "deliveryIds"},
                        "deliveryIds": [
                            {"courierName": d.get("courierName")}
                            for d in s.get("deliveryIds") or []
                        ],
                    }
                    for s in logistica[0].get("slas") or []
                ]
            }
        ]
        if logistica
        else [],
        "paymentData": {
            "installmentOptions": [
                {
                    "paymentName": o.get("paymentName"),
                    "paymentGroupName": o.get("paymentGroupName"),
                    "installments": [
                        {k: i.get(k) for k in ("count", "value", "total", "interestRate")}
                        for i in o.get("installments") or []
                    ],
                }
                for o in opcoes
                if o.get("paymentGroupName") in (GRUPO_CARTAO, "instantPaymentPaymentGroup")
                or "pix" in (o.get("paymentName") or "").lower()
            ]
        },
    }


def _com_sku(link: str, sku: str) -> str:
    partes = urlsplit(link)
    if "skuId=" in partes.query:
        return link
    consulta = f"{partes.query}&skuId={quote(sku)}" if partes.query else f"skuId={quote(sku)}"
    return urlunsplit(partes._replace(query=consulta))


def _conservadora(
    oferta: Oferta, primeira: dict[str, Any], segunda: dict[str, Any], tem_cep: bool
) -> tuple[dict[str, Any], bool]:
    totais = []
    for dados in (primeira, segunda):
        sonda = replace(oferta, alertas=[], frete=Frete.desconhecido())
        aplicar_simulacao(sonda, dados, tem_cep=tem_cep)
        sonda.consolidar()
        totais.append((sonda.total, sonda.preco, sonda.preco_pix, sonda.frete.status, dados))
    (total_a, *resto_a, dados_a), (total_b, *resto_b, dados_b) = totais
    cotada_a = resto_a[2] is StatusFrete.CALCULADO
    cotada_b = resto_b[2] is StatusFrete.CALCULADO
    if cotada_a != cotada_b:
        return (dados_a if cotada_a else dados_b), True
    if not cotada_a:
        return dados_a, True
    estavel = (total_a, *resto_a) == (total_b, *resto_b)
    return (dados_a if total_a >= total_b else dados_b), estavel


def aplicar_simulacao(
    oferta: Oferta, dados: dict[str, Any], *, tem_cep: bool, cotada_em: float | None = None
) -> None:
    itens = dados.get("items") or []
    if not itens:
        oferta.disponivel = False
        oferta.frete = Frete.desconhecido()
        return
    item = itens[0]
    cartao, pix, parcelamentos = _pagamento_checkout(dados.get("paymentData") or {})
    imposto = sum(t.get("value") or 0 for t in dados.get("totals") or [] if t.get("id") == "Tax")
    vitrine = item.get("sellingPrice") or item.get("price")
    preco = cartao or (vitrine + imposto if vitrine else None)
    if preco:
        if abs(preco - oferta.preco) > oferta.preco * DESVIO_DE_PRECO:
            oferta.alertar(Alerta.PRECO_MUDOU_NO_CHECKOUT)
        oferta.preco = preco
    if item.get("listPrice"):
        oferta.preco_original = item["listPrice"] + imposto

    oferta.preco_pix = pix
    if parcelamentos is not None:
        oferta.parcelamento = parcelamentos

    disponibilidade = item.get("availability")
    if disponibilidade == "cannotBeDelivered":
        oferta.frete = Frete(StatusFrete.NAO_ENTREGA if tem_cep else StatusFrete.SEM_CEP)
        return
    if disponibilidade != "available":
        oferta.disponivel = False
        oferta.frete = Frete.desconhecido()
        return
    if not tem_cep:
        oferta.frete = Frete(StatusFrete.SEM_CEP)
        return

    logistica = dados.get("logisticsInfo") or []
    opcoes = [_opcao(sla) for sla in (logistica[0].get("slas") or [])] if logistica else []
    opcoes.sort(key=lambda o: (o.tipo != "entrega", o.valor, o.prazo_dias or 0))
    melhor = entrega_mais_barata(opcoes)
    if melhor is None:
        oferta.frete = Frete(StatusFrete.NAO_ENTREGA, opcoes=opcoes)
        return
    oferta.frete = Frete(
        StatusFrete.CALCULADO,
        valor=melhor.valor,
        prazo=melhor.prazo,
        prazo_dias=melhor.prazo_dias,
        opcoes=opcoes,
        modalidade=melhor.nome,
        transportadora=melhor.transportadora,
        entrega_ate=melhor.entrega_ate,
        cotado_em=datetime.fromtimestamp(cotada_em or time.time(), UTC).isoformat(
            timespec="seconds"
        ),
    )


def _opcao(sla: dict[str, Any]) -> OpcaoFrete:
    retirada = sla.get("deliveryChannel") == "pickup-in-point"
    nome = sla.get("name") or sla.get("id") or ""
    if retirada:
        informacao = sla.get("pickupStoreInfo") or {}
        nome = informacao.get("friendlyName") or _ID_INTERNO.sub("", nome)
    prazo, dias = ler_prazo(sla.get("shippingEstimate"))
    transportadoras = [
        d.get("courierName") for d in sla.get("deliveryIds") or [] if d.get("courierName")
    ]
    data = sla.get("shippingEstimateDate")
    distancia = sla.get("pickupDistance")
    return OpcaoFrete(
        nome=nome,
        valor=(sla.get("price") or 0) + (sla.get("tax") or 0),
        prazo=prazo,
        prazo_dias=dias,
        tipo="retirada" if retirada else "entrega",
        transportadora=", ".join(dict.fromkeys(transportadoras)) or None,
        entrega_ate=data[:10] if data else None,
        distancia_km=round(distancia, 1) if retirada and distancia else None,
    )


def _pagamento_catalogo(opcoes: list[dict[str, Any]]) -> tuple[int | None, Parcelamento | None]:
    pix = None
    melhor: Parcelamento | None = None
    for opcao in opcoes:
        nome = (opcao.get("PaymentSystemName") or "").lower()
        quantidade = opcao.get("NumberOfInstallments") or 0
        total = opcao.get("TotalValuePlusInterestRate")
        if total is None or quantidade < 1:
            continue
        if nome == "pix" and quantidade == 1:
            centavos = para_centavos(total)
            pix = centavos if pix is None else min(pix, centavos)
            continue
        if opcao.get("PaymentSystemGroupName") != GRUPO_CARTAO:
            continue
        candidata = Parcelamento(
            parcelas=quantidade,
            valor=para_centavos(opcao.get("Value") or 0),
            total=para_centavos(total),
            juros=bool(opcao.get("InterestRate")),
        )
        melhor = _melhor_parcelamento(melhor, candidata)
    return pix, melhor


def _pagamento_checkout(
    pagamento: dict[str, Any],
) -> tuple[int | None, int | None, Parcelamento | None]:
    cartao = None
    pix = None
    melhor: Parcelamento | None = None
    for opcao in pagamento.get("installmentOptions") or []:
        nome = (opcao.get("paymentName") or "").lower()
        parcelamentos = opcao.get("installments") or []
        if "pix" in nome:
            avista_unicas = [
                i["total"] for i in parcelamentos if i.get("count") == 1 and "total" in i
            ]
            if avista_unicas:
                pix = min(avista_unicas) if pix is None else min(pix, *avista_unicas)
            continue
        if opcao.get("paymentGroupName") != GRUPO_CARTAO:
            continue
        for parcela in parcelamentos:
            if not parcela.get("count") or parcela.get("total") is None:
                continue
            if parcela["count"] == 1:
                cartao = parcela["total"] if cartao is None else min(cartao, parcela["total"])
            candidata = Parcelamento(
                parcelas=parcela["count"],
                valor=parcela.get("value") or 0,
                total=parcela["total"],
                juros=bool(parcela.get("interestRate")),
            )
            melhor = _melhor_parcelamento(melhor, candidata)
    return cartao, pix, melhor


def _melhor_parcelamento(atual: Parcelamento | None, novo: Parcelamento) -> Parcelamento:
    if atual is None:
        return novo
    return min(atual, novo, key=lambda i: (i.juros, -i.parcelas, i.total))
