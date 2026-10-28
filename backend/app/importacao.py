from decimal import ROUND_HALF_UP, Decimal

from app.modelos import Importacao

_CENTAVO = Decimal("1")


def _reais(centavos_usd: int, cotacao: float) -> int:
    return int((Decimal(centavos_usd) * Decimal(str(cotacao))).quantize(_CENTAVO, ROUND_HALF_UP))


def estimar_importacao(
    produto_usd: int,
    frete_usd: int | None,
    cotacao_dolar: float,
    aliquota_importacao: float,
    aliquota_icms: float,
) -> tuple[int, int | None, Importacao]:
    produto = _reais(produto_usd, cotacao_dolar)
    frete = _reais(frete_usd, cotacao_dolar) if frete_usd is not None else None
    valor_aduaneiro = Decimal(produto + (frete or 0))
    imposto = (valor_aduaneiro * Decimal(str(aliquota_importacao))).quantize(
        _CENTAVO, ROUND_HALF_UP
    )
    taxa_icms = Decimal(str(aliquota_icms))
    base_icms = (valor_aduaneiro + imposto) / (1 - taxa_icms)
    icms = (base_icms * taxa_icms).quantize(_CENTAVO, ROUND_HALF_UP)
    return (
        produto,
        frete,
        Importacao(
            produto_usd=produto_usd,
            frete_usd=frete_usd,
            cotacao_dolar=cotacao_dolar,
            imposto_importacao=int(imposto),
            icms=int(icms),
        ),
    )
