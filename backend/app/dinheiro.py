import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CENTAVO = Decimal("0.01")
_REAIS = re.compile(r"-?\d+(?:\.\d{3})*(?:,\d{1,2})?")


def para_centavos(valor: float | int | str | Decimal) -> int:
    if isinstance(valor, float):
        valor = repr(valor)
    try:
        quantia = Decimal(valor).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"valor monetário inválido: {valor!r}") from None
    return int(quantia * 100)


def ler_reais(texto: str) -> int:
    achado = _REAIS.search(texto.replace("\xa0", " "))
    if not achado:
        raise ValueError(f"valor monetário inválido: {texto!r}")
    return para_centavos(achado.group().replace(".", "").replace(",", "."))
