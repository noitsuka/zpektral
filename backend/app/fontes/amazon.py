import html
import re
import time
from dataclasses import dataclass
from urllib.parse import quote_plus

from app.cliente_http import ClienteHttp, ErroExterno
from app.configuracao import Configuracoes
from app.dinheiro import ler_reais
from app.fontes.base import (
    ContextoBusca,
    Previa,
    cotar_pelo_navegador,
    escolher_para_cotar,
    montar_ofertas,
)
from app.modelos import Frete, Loja, Oferta, Origem, Parcelamento, StatusFrete
from app.navegador.amazon import FreteAmazonNavegador

SITE = "https://www.amazon.com.br"
PATROCINADO = re.compile(r"^An[uú]ncio patrocinado\s*[\u2013\u2014-]\s*", re.I)
_BLOCO = re.compile(r'data-component-type="s-search-result"')
_ASIN = re.compile(r'data-asin="([A-Z0-9]{10})"')
_TITULO = re.compile(r'<h2[^>]*\baria-label="([^"]+)"')
_PRECO = re.compile(r'<span class="a-price"[^>]*><span class="a-offscreen">([^<]+)<')
_PRECO_DE = re.compile(r'data-a-strike="true"[^>]*><span class="a-offscreen">([^<]+)<')
_IMAGEM = re.compile(r'<img class="s-image" src="(https://[^"]+)"')
_ENTREGA = re.compile(r'udm-primary-delivery-message"><div[^>]*>(.*?)</div>', re.S)
_PARCELAS = re.compile(
    r"em at[eé] (\d{1,2})x de </span>.{0,200}?<span class=\"a-offscreen\">([^<]+)<", re.S
)
_TAGS = re.compile(r"<[^>]+>")
_VERIFICACAO = ("/errors/validateCaptcha", "api-services-support@amazon.com")


@dataclass(frozen=True)
class Resultado:
    asin: str
    titulo: str
    preco: int
    preco_original: int | None
    imagem: str | None
    entrega: str | None
    frete_gratis: bool
    parcelas: int | None
    valor_parcela: int | None
    patrocinado: bool


def _asin(oferta: Oferta) -> str:
    return oferta.id.split(":", 1)[1]


def url_de_busca(texto: str) -> str:
    return f"{SITE}/s?k={quote_plus(texto)}"


def _texto(trecho: str) -> str:
    return " ".join(html.unescape(_TAGS.sub(" ", trecho)).split())


def _ler_bloco(bloco: str) -> Resultado | None:
    asin = _ASIN.search(bloco)
    titulo = _TITULO.search(bloco)
    preco = _PRECO.search(bloco)
    if not (asin and titulo and preco):
        return None
    nome = html.unescape(titulo.group(1)).strip()
    patrocinado = bool(PATROCINADO.match(nome))
    entrega = _ENTREGA.search(bloco)
    texto_entrega = _texto(entrega.group(1)) if entrega else None
    gratis = bool(
        texto_entrega
        and "GRÁTIS" in texto_entrega.upper()
        and "PRIMEIRO PEDIDO" not in texto_entrega.upper()
    )
    de = _PRECO_DE.search(bloco)
    parcelas = _PARCELAS.search(bloco)
    imagem = _IMAGEM.search(bloco)
    valor_parcela = ler_reais(html.unescape(parcelas.group(2))) if parcelas else None
    return Resultado(
        asin=asin.group(1),
        titulo=PATROCINADO.sub("", nome),
        preco=ler_reais(html.unescape(preco.group(1))),
        preco_original=ler_reais(html.unescape(de.group(1))) if de else None,
        imagem=imagem.group(1) if imagem else None,
        entrega=texto_entrega,
        frete_gratis=gratis,
        parcelas=int(parcelas.group(1)) if parcelas else None,
        valor_parcela=valor_parcela,
        patrocinado=patrocinado,
    )


def ler_resultados(pagina: bytes) -> list[Resultado]:
    texto = pagina.decode("utf-8", errors="replace")
    if any(marca in texto for marca in _VERIFICACAO):
        raise ErroExterno("amazon: página de verificação de robô; não é contornada")
    inicios = [texto.rfind("<div", 0, m.start()) for m in _BLOCO.finditer(texto)]
    blocos = [texto[a:b] for a, b in zip(inicios, [*inicios[1:], len(texto)], strict=True)]
    por_asin: dict[str, Resultado] = {}
    for bloco in blocos:
        resultado = _ler_bloco(bloco)
        if resultado is None:
            continue
        atual = por_asin.get(resultado.asin)
        if atual is None or (atual.patrocinado and not resultado.patrocinado):
            por_asin[resultado.asin] = resultado
    return list(por_asin.values())


class FonteAmazon:
    id = "amazon"
    nome = "Amazon"

    def __init__(
        self,
        http: ClienteHttp,
        config: Configuracoes,
        frete: FreteAmazonNavegador | None = None,
    ):
        self._http = http
        self._config = config
        self._frete = frete
        self._ref = Loja(self.id, self.nome)

    @property
    def ativa(self) -> bool:
        return self._config.amazon_busca_publica

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        inicio = time.monotonic()
        resposta = await self._http.requisitar(
            "GET",
            url_de_busca(ctx.texto),
            tentativas=0,
            headers={"accept-language": "pt-BR,pt;q=0.9"},
        )
        resultados = ler_resultados(resposta.content)
        ofertas = montar_ofertas(self.id, resultados, lambda r, p: self._oferta(r, p, ctx))
        if self._frete is None or ctx.endereco is None:
            return ofertas
        alvo = escolher_para_cotar(
            ofertas,
            self._config.relevancia_minima_cotacao,
            self._config.navegador_cotacoes,
            lambda o: o,
        )
        if not alvo:
            return ofertas
        frete, cep = self._frete, ctx.endereco.cep
        orcamento = self._config.segundos_limite_fonte - (time.monotonic() - inicio) - 0.5
        return await cotar_pelo_navegador(
            ofertas,
            alvo,
            ctx,
            previa,
            orcamento,
            lambda destino: frete.cotar([_asin(o) for o in alvo], cep, destino),
            _asin,
        )

    def _oferta(self, r: Resultado, posicao: int, ctx: ContextoBusca) -> Oferta:
        parcelamento = None
        if r.parcelas and r.valor_parcela:
            total = r.parcelas * r.valor_parcela
            parcelamento = Parcelamento(
                parcelas=r.parcelas,
                valor=r.valor_parcela,
                total=total,
                juros=total > r.preco + r.parcelas,
            )
        return Oferta(
            id=f"{self.id}:{r.asin}",
            titulo=r.titulo,
            link=f"{SITE}/dp/{r.asin}",
            loja=self._ref,
            preco=r.preco,
            origem=Origem.MARKETPLACE,
            imagem=r.imagem,
            preco_original=r.preco_original,
            parcelamento=parcelamento,
            frete=(
                Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0)
                if r.frete_gratis
                else ctx.frete_sem_cotacao()
            ),
            relevancia=ctx.relevancia_de(r.titulo),
            posicao=posicao,
        )
