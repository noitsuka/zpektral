from datetime import UTC, datetime, timedelta

from app.cache import CacheComValidade
from app.cliente_http import ClienteHttp, ErroExterno

PTAX = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)
DIAS_DE_JANELA = 10
SEGUNDOS_CACHE = 3 * 3600


class ServicoCambio:
    def __init__(self, http: ClienteHttp, relogio=lambda: datetime.now(UTC)):
        self._http = http
        self._relogio = relogio
        self._cache: CacheComValidade[str, float] = CacheComValidade(SEGUNDOS_CACHE, 4)

    async def dolar(self) -> float:
        return await self._cache.obter_ou_carregar("USD", self._buscar_ptax)

    async def _buscar_ptax(self) -> float:
        hoje = self._relogio().date()
        inicio = hoje - timedelta(days=DIAS_DE_JANELA)
        dados = await self._http.obter_json(
            PTAX,
            params={
                "@dataInicial": f"'{inicio:%m-%d-%Y}'",
                "@dataFinalCotacao": f"'{hoje:%m-%d-%Y}'",
                "$format": "json",
                "$select": "cotacaoVenda,dataHoraCotacao",
            },
        )
        cotacoes = dados.get("value") if isinstance(dados, dict) else None
        validas = [
            c
            for c in cotacoes or []
            if isinstance(c, dict)
            and isinstance(c.get("cotacaoVenda"), int | float)
            and c["cotacaoVenda"] > 0
            and isinstance(c.get("dataHoraCotacao"), str)
        ]
        if not validas:
            raise ErroExterno("banco central: cotação do dólar indisponível")
        return float(max(validas, key=lambda c: c["dataHoraCotacao"])["cotacaoVenda"])
