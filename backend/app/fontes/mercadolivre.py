import asyncio
import hashlib
import logging
import math
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.configuracao import Configuracoes
from app.credenciais import GuardaCredenciais
from app.dinheiro import para_centavos
from app.fontes.base import (
    ContextoBusca,
    Previa,
    entrega_mais_barata,
    escolher_para_cotar,
    executar_no_prazo,
    montar_ofertas,
)
from app.modelos import (
    Frete,
    Loja,
    Oferta,
    OpcaoFrete,
    Origem,
    Parcelamento,
    StatusFrete,
)

log = logging.getLogger("zpektral.mercadolivre")

API = "https://api.mercadolibre.com"
LIMITE_BUSCA = 50


REAUTORIZAR = (
    "mercado livre: a autorização expirou ou foi revogada; autorize de novo com "
    "python -m scripts.autorizar_mercadolivre"
)


def _resumo(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


class CofreTokens:
    """Access token em memória; o refresh token, que o Mercado Livre troca a cada renovação,
    fica cifrado no banco para valer em todas as instâncias.

    O ML_TOKEN_RENOVACAO do ambiente é a semente: enquanto o banco guarda tokens nascidos dela,
    vale o do banco; trocar a variável (nova autorização) recomeça a partir dela."""

    fonte = "mercadolivre"

    def __init__(
        self,
        http: ClienteHttp,
        config: Configuracoes,
        guarda: GuardaCredenciais | None = None,
        relogio=time.time,
    ):
        self._http = http
        self._config = config
        self._guarda = guarda
        self._relogio = relogio
        self._trava = asyncio.Lock()
        self._acesso: str | None = None
        self._expira = 0.0
        self._rejeitado: str | None = None
        self._recusado: str | None = None
        semente = config.ml_token_renovacao.get_secret_value()
        self._renovacao = semente
        self._semente = _resumo(semente) if semente else None

    @property
    def configurado(self) -> bool:
        s = self._config
        return bool(s.ml_id_cliente and s.ml_segredo_cliente.get_secret_value() and self._semente)

    def invalidar(self, rejeitado: str) -> None:
        self._rejeitado = rejeitado
        if self._acesso == rejeitado:
            self._acesso, self._expira = None, 0.0

    async def obter_token(self) -> str:
        if self._acesso and self._relogio() < self._expira:
            return self._acesso
        async with self._trava:
            if self._acesso and self._relogio() < self._expira:
                return self._acesso
            if self._guarda is None:
                self._adotar(await self._renovar(self._renovacao))
                return self._acesso
            async with self._guarda.travar(self.fonte) as travada:
                salvo = travada.atual
                if not salvo or salvo.get("semente") != self._semente:
                    salvo = None
                if salvo and self._utilizavel(salvo):
                    self._adotar(salvo)
                else:
                    renovacao = salvo.get("refresh_token") if salvo else None
                    travada.novo = await self._renovar(renovacao or self._renovacao)
                    self._adotar(travada.novo)
            return self._acesso

    def _utilizavel(self, salvo: dict[str, Any]) -> bool:
        acesso, expira = salvo.get("access_token"), salvo.get("expires_at")
        return (
            isinstance(acesso, str)
            and acesso != self._rejeitado
            and isinstance(expira, int | float)
            and self._relogio() < expira
        )

    def _adotar(self, dados: dict[str, Any]) -> None:
        self._acesso, self._expira = dados["access_token"], float(dados["expires_at"])
        self._renovacao = dados["refresh_token"]

    async def _renovar(self, renovacao: str) -> dict[str, Any]:
        if self._recusado == _resumo(renovacao):
            raise ErroExterno(REAUTORIZAR, 401)
        resposta = await self._http.requisitar(
            "POST",
            f"{API}/oauth/token",
            tentativas=0,
            aceitos=(200, 400, 401),
            data={
                "grant_type": "refresh_token",
                "client_id": self._config.ml_id_cliente,
                "client_secret": self._config.ml_segredo_cliente.get_secret_value(),
                "refresh_token": renovacao,
            },
        )
        corpo = ler_json(resposta)
        corpo = corpo if isinstance(corpo, dict) else {}
        if resposta.status_code != 200:
            if corpo.get("error") == "invalid_grant":
                self._recusado = _resumo(renovacao)
                raise ErroExterno(REAUTORIZAR, 401)
            motivo = str(corpo.get("error") or "sem motivo")[:60]
            raise ErroExterno(
                f"mercado livre: renovação do token recusada (HTTP {resposta.status_code}, "
                f"{motivo}); confira ML_ID_CLIENTE e ML_SEGREDO_CLIENTE",
                resposta.status_code,
            )
        acesso = corpo.get("access_token")
        if not isinstance(acesso, str) or not acesso:
            raise ErroExterno("mercado livre: resposta de token sem access_token")
        nova = corpo.get("refresh_token")
        validade = corpo.get("expires_in")
        validade = validade if isinstance(validade, int) and validade > 0 else 21600
        return {
            "access_token": acesso,
            "refresh_token": nova if isinstance(nova, str) and nova else renovacao,
            "expires_at": self._relogio() + max(60, validade - 300),
            "semente": self._semente,
        }


class FonteMercadoLivre:
    id = "mercadolivre"
    nome = "Mercado Livre"

    def __init__(
        self, http: ClienteHttp, config: Configuracoes, credenciais: GuardaCredenciais | None = None
    ):
        self._http = http
        self._config = config
        self._cofre = CofreTokens(http, config, credenciais)
        self._ref = Loja(self.id, self.nome)

    @property
    def ativa(self) -> bool:
        return self._cofre.configurado

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        inicio = time.monotonic()
        url = f"{API}/sites/MLB/search?q={quote(ctx.texto)}&limit={LIMITE_BUSCA}"
        token = await self._cofre.obter_token()
        resposta = await self._http.requisitar(
            "GET", url, aceitos=(200, 401, 403), headers={"authorization": f"Bearer {token}"}
        )
        if resposta.status_code == 401:
            self._cofre.invalidar(token)
            token = await self._cofre.obter_token()
            resposta = await self._http.requisitar(
                "GET", url, aceitos=(200, 403), headers={"authorization": f"Bearer {token}"}
            )
        if resposta.status_code == 403:
            raise ErroExterno(
                "mercado livre: busca recusada (HTTP 403); confira se o app tem acesso à busca", 403
            )
        dados = ler_json(resposta)
        if not isinstance(dados, dict):
            raise ErroExterno("mercado livre: resposta de busca inesperada")
        ofertas = montar_ofertas(
            self.id, dados.get("results") or [], lambda item, p: self._oferta(item, p, ctx)
        )

        a_cotar = escolher_para_cotar(
            ofertas,
            self._config.relevancia_minima_cotacao,
            self._config.cotacoes_por_loja,
            lambda o: o,
        )
        if ctx.endereco is not None:
            if previa is not None and a_cotar:
                for o in a_cotar:
                    o.frete = ctx.frete_calculando()
                previa([o.consolidar() for o in ofertas])
            orcamento = self._config.segundos_limite_fonte - (time.monotonic() - inicio) - 0.5
            await executar_no_prazo(
                orcamento, [self._cotar(o, ctx.endereco.cep, token) for o in a_cotar]
            )
            for o in a_cotar:
                if o.frete.status is StatusFrete.CALCULANDO:
                    o.frete = ctx.frete_sem_cotacao()
        return [o.consolidar() for o in ofertas]

    def _oferta(self, item: dict[str, Any], posicao: int, ctx: ContextoBusca) -> Oferta | None:
        if not item.get("price"):
            return None
        info_frete = item.get("shipping") or {}
        if info_frete.get("free_shipping"):
            frete = Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0)
        else:
            frete = ctx.frete_sem_cotacao()
        parcela = item.get("installments") or {}
        parcelamentos = None
        if parcela.get("quantity") and parcela.get("amount"):
            valor = para_centavos(parcela["amount"])
            parcelamentos = Parcelamento(
                parcelas=parcela["quantity"],
                valor=valor,
                total=valor * parcela["quantity"],
                juros=bool(parcela.get("rate")),
            )
        vendedor = item.get("official_store_name") or (item.get("seller") or {}).get("nickname")
        titulo = item.get("title") or ""
        if item.get("condition") == "used":
            titulo = f"{titulo} (usado)"
        original = item.get("original_price")
        return Oferta(
            id=f"{self.id}:{item.get('id')}",
            titulo=titulo,
            link=item.get("permalink") or "",
            loja=self._ref,
            preco=para_centavos(item["price"]),
            origem=Origem.MARKETPLACE,
            vendedor=vendedor,
            imagem=(item.get("thumbnail") or "").replace("http://", "https://") or None,
            preco_original=para_centavos(original) if original else None,
            parcelamento=parcelamentos,
            frete=frete,
            relevancia=ctx.relevancia_de(titulo, vendedor),
            posicao=posicao,
        )

    async def _cotar(self, oferta: Oferta, cep: str, token: str) -> None:
        id_item = oferta.id.split(":", 1)[1]
        url = f"{API}/items/{quote(id_item, safe='')}/shipping_options?zip_code={cep}"
        try:
            resposta = await self._http.requisitar(
                "GET", url, aceitos=(200, 401), headers={"authorization": f"Bearer {token}"}
            )
            if resposta.status_code == 401:
                self._cofre.invalidar(token)
                token = await self._cofre.obter_token()
                resposta = await self._http.requisitar(
                    "GET", url, headers={"authorization": f"Bearer {token}"}
                )
            dados = ler_json(resposta)
        except ErroExterno:
            return
        if not isinstance(dados, dict):
            return
        opcoes = [_opcao(o) for o in dados.get("options") or []]
        melhor = entrega_mais_barata(opcoes)
        if melhor is None:
            oferta.frete = Frete(StatusFrete.NAO_ENTREGA)
        else:
            opcoes.sort(key=lambda o: (o.valor, o.prazo_dias or 0))
            oferta.frete = Frete(
                StatusFrete.CALCULADO,
                valor=melhor.valor,
                prazo=melhor.prazo,
                prazo_dias=melhor.prazo_dias,
                opcoes=opcoes,
                modalidade=melhor.nome,
                cotado_em=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        oferta.consolidar()


def _opcao(bruto: dict[str, Any]) -> OpcaoFrete:
    dias = None
    eta = bruto.get("estimated_delivery_time") or {}
    if eta.get("date"):
        try:
            entrega = datetime.fromisoformat(eta["date"])
            if entrega.tzinfo is None:
                entrega = entrega.replace(tzinfo=UTC)
            dias = max(0, math.ceil((entrega - datetime.now(UTC)).total_seconds() / 86400))
        except (TypeError, ValueError):
            dias = None
    prazo = None if dias is None else (f"até {dias} dia" if dias == 1 else f"até {dias} dias")
    return OpcaoFrete(
        nome=bruto.get("name") or "Entrega",
        valor=para_centavos(bruto.get("cost") or 0),
        prazo=prazo,
        prazo_dias=dias,
        tipo="entrega",
    )
