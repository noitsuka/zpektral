import asyncio
import json
import logging
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.configuracao import Configuracoes
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


class CofreTokens:
    def __init__(self, http: ClienteHttp, config: Configuracoes, relogio=time.time):
        self._http = http
        self._config = config
        self._relogio = relogio
        self._caminho = Path(config.ml_arquivo_token)
        self._trava = asyncio.Lock()
        self._acesso: str | None = None
        self._expira = 0.0
        self._renovacao = config.ml_token_renovacao.get_secret_value()
        salvo = self._ler()
        if isinstance(salvo.get("refresh_token"), str) and salvo["refresh_token"]:
            self._renovacao = salvo["refresh_token"]
            acesso, expira = salvo.get("access_token"), salvo.get("expires_at")
            if isinstance(acesso, str) and isinstance(expira, int | float):
                self._acesso, self._expira = acesso, float(expira)

    @property
    def configurado(self) -> bool:
        s = self._config
        return bool(s.ml_id_cliente and s.ml_segredo_cliente.get_secret_value() and self._renovacao)

    def invalidar(self, rejeitado: str) -> None:
        if self._acesso == rejeitado:
            self._acesso, self._expira = None, 0.0

    async def obter_token(self) -> str:
        if self._acesso and self._relogio() < self._expira:
            return self._acesso
        async with self._trava:
            if self._acesso and self._relogio() < self._expira:
                return self._acesso
            resposta = await self._http.requisitar(
                "POST",
                f"{API}/oauth/token",
                tentativas=0,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._config.ml_id_cliente,
                    "client_secret": self._config.ml_segredo_cliente.get_secret_value(),
                    "refresh_token": self._renovacao,
                },
            )
            corpo = ler_json(resposta)
            acesso = corpo.get("access_token") if isinstance(corpo, dict) else None
            if not isinstance(acesso, str) or not acesso:
                raise ErroExterno("mercado livre: resposta de token sem access_token")
            renovacao = corpo.get("refresh_token")
            if isinstance(renovacao, str) and renovacao:
                self._renovacao = renovacao
            validade = corpo.get("expires_in")
            validade = validade if isinstance(validade, int) and validade > 0 else 21600
            self._acesso = acesso
            self._expira = self._relogio() + max(60, validade - 300)
            self._escrever()
            return acesso

    def _ler(self) -> dict[str, Any]:
        try:
            return json.loads(self._caminho.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _escrever(self) -> None:
        corpo = {
            "access_token": self._acesso,
            "refresh_token": self._renovacao,
            "expires_at": self._expira,
        }
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        try:
            descritor = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
                json.dump(corpo, arquivo)
            os.replace(temporario, self._caminho)
        except OSError as excecao:
            log.warning("não foi possível salvar o token do mercado livre: %s", excecao)


class FonteMercadoLivre:
    id = "mercadolivre"
    nome = "Mercado Livre"

    def __init__(self, http: ClienteHttp, config: Configuracoes, cofre: CofreTokens | None = None):
        self._http = http
        self._config = config
        self._cofre = cofre if cofre is not None else CofreTokens(http, config)
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
                "mercado livre: busca recusada (HTTP 403); confira se o app tem acesso à busca"
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
