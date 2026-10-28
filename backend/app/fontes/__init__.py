from app.cache import CacheComValidade
from app.cambio import ServicoCambio
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes
from app.fontes.amazon import FonteAmazon
from app.fontes.base import ContextoBusca, Fonte
from app.fontes.buscape import FonteBuscape
from app.fontes.ebay import FonteEbay
from app.fontes.kabum import FonteKabum
from app.fontes.mercadolivre import FonteMercadoLivre
from app.fontes.shopee import FonteShopee
from app.fontes.vtex import FonteVtex, carregar_lojas
from app.navegador.amazon import FreteAmazonNavegador
from app.navegador.base import Navegador
from app.navegador.shopee import FreteShopeeNavegador

__all__ = ["ContextoBusca", "Fonte", "criar_fontes"]


def criar_fontes(
    http: ClienteHttp, config: Configuracoes, navegador: Navegador | None = None
) -> list[Fonte]:
    frete_amazon = (
        FreteAmazonNavegador(navegador, config)
        if navegador is not None and config.amazon_frete_navegador
        else None
    )
    frete_shopee = (
        FreteShopeeNavegador(navegador, config)
        if navegador is not None and config.shopee_frete_navegador
        else None
    )
    cotacoes = CacheComValidade(config.segundos_cache_cotacao, config.entradas_cache_cotacao)
    vtex: list[Fonte] = [FonteVtex(loja, http, config, cotacoes) for loja in carregar_lojas()]
    diretas: list[Fonte] = [
        *vtex,
        FonteKabum(http, config),
        FonteMercadoLivre(http, config),
        FonteShopee(http, config, frete=frete_shopee),
        FonteAmazon(http, config, frete=frete_amazon),
    ]
    importados: list[Fonte] = [FonteEbay(http, config, ServicoCambio(http))]
    cobertas = [s.nome for s in diretas if s.ativa]
    return [*diretas, FonteBuscape(http, config, lojas_diretas=cobertas), *importados]
