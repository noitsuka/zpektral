import asyncio
import hashlib
import logging
import math
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

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
    Condicao,
    Frete,
    Loja,
    Oferta,
    OpcaoFrete,
    Origem,
    StatusFrete,
)
from app.relevancia import normalizar_ean

log = logging.getLogger("zpektral.mercadolivre")

API = "https://api.mercadolibre.com"
SITE = "https://produto.mercadolivre.com.br"
PRODUTOS_DO_CATALOGO = 10
# cada produto custa uma chamada a mais; as ofertas de cada um disputam a mesma página
PRODUTOS_COM_OFERTAS = 6
OFERTAS_POR_PRODUTO = 3


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
        self._tarefa: asyncio.Future[None] | None = None
        self._acesso: str | None = None
        self._expira = 0.0
        self._rejeitado: str | None = None
        self._recusados: set[str] = set()
        semente = config.ml_token_renovacao.get_secret_value()
        self._renovacao = semente
        self._semente = _resumo(semente) if semente else None

    @property
    def configurado(self) -> bool:
        s = self._config
        # com várias instâncias e sem o cofre, a primeira renovação queimaria a semente das outras
        return bool(
            s.ml_id_cliente
            and s.ml_segredo_cliente.get_secret_value()
            and self._semente
            and (self._guarda is not None or not s.url_banco)
        )

    def invalidar(self, rejeitado: str) -> None:
        self._rejeitado = rejeitado
        if self._acesso == rejeitado:
            self._acesso, self._expira = None, 0.0

    async def obter_token(self) -> str:
        if self._acesso and self._relogio() < self._expira:
            return self._acesso
        if self._tarefa is None or self._tarefa.done():
            self._tarefa = asyncio.ensure_future(self._atualizar())
            self._tarefa.add_done_callback(lambda t: t.cancelled() or t.exception())
        # quando o Mercado Livre responde, o token antigo já morreu: a busca cancelada no meio
        # não pode impedir que o novo seja guardado
        await asyncio.shield(self._tarefa)
        return self._acesso

    async def _atualizar(self) -> None:
        if self._acesso and self._relogio() < self._expira:
            return
        if self._guarda is None:
            self._adotar(await self._renovar(self._renovacao))
            return
        async with self._guarda.travar(self.fonte) as travada:
            salvo = travada.atual
            if not salvo or salvo.get("semente") != self._semente:
                salvo = None
            if salvo and self._utilizavel(salvo):
                self._adotar(salvo)
                return
            renovacao = (salvo or {}).get("refresh_token") or self._renovacao
            try:
                travada.novo = await self._renovar(renovacao)
            except ErroExterno:
                # o banco pode ter perdido a gravação de um token que esta instância já trocou
                if renovacao == self._renovacao or _resumo(self._renovacao) == self._semente:
                    raise
                travada.novo = await self._renovar(self._renovacao)
            self._adotar(travada.novo)

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
        if _resumo(renovacao) in self._recusados:
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
                self._recusados.add(_resumo(renovacao))
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
        # /sites/MLB/search saiu da documentação em 2025 e recusa apps novos com 403; o caminho
        # documentado é o catálogo e, para cada produto, as ofertas que disputam a página dele
        inicio = time.monotonic()
        token = await self._cofre.obter_token()
        url = (
            f"{API}/products/search?status=active&site_id=MLB&q={quote(ctx.texto)}"
            f"&limit={PRODUTOS_DO_CATALOGO}"
        )
        resposta, token = await self._consultar(url, token)
        if resposta.status_code == 403:
            raise ErroExterno(
                "mercado livre: catálogo recusado (HTTP 403); o app precisa da permissão "
                "Publicação e sincronização",
                403,
            )
        dados = ler_json(resposta)
        if not isinstance(dados, dict):
            raise ErroExterno("mercado livre: resposta de busca inesperada")
        produtos = [p for p in dados.get("results") or [] if isinstance(p, dict) and p.get("id")]
        # só o produto que casa com a busca gasta a chamada das ofertas
        notas = [ctx.relevancia_de(str(p.get("name") or ""), None) for p in produtos]
        escolhidos = [
            p
            for p, nota in sorted(zip(produtos, notas, strict=True), key=lambda par: -par[1])
            if nota >= self._config.relevancia_minima_cotacao
        ][:PRODUTOS_COM_OFERTAS]
        listas = await asyncio.gather(
            *(self._itens(p["id"], token) for p in escolhidos), return_exceptions=True
        )
        falhas = [r for r in listas if isinstance(r, BaseException)]
        if escolhidos and len(falhas) == len(escolhidos):
            bloqueio = next((f for f in falhas if getattr(f, "bloqueio", False)), None)
            raise bloqueio or falhas[0]
        pares = [
            (produto, item)
            for produto, itens in zip(escolhidos, listas, strict=True)
            if not isinstance(itens, BaseException)
            for item in itens
        ]
        vendedores = await self._vendedores({item.get("seller_id") for _, item in pares}, token)
        ofertas = montar_ofertas(
            self.id, pares, lambda par, pos: self._oferta(*par, pos, ctx, vendedores)
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

    async def _consultar(self, url: str, token: str) -> tuple[httpx.Response, str]:
        cabecalho = {"authorization": f"Bearer {token}"}
        resposta = await self._http.requisitar(
            "GET", url, aceitos=(200, 401, 403), headers=cabecalho
        )
        if resposta.status_code == 401:
            self._cofre.invalidar(token)
            token = await self._cofre.obter_token()
            resposta = await self._http.requisitar(
                "GET", url, aceitos=(200, 403), headers={"authorization": f"Bearer {token}"}
            )
        return resposta, token

    async def _itens(self, id_produto: str, token: str) -> list[dict[str, Any]]:
        url = f"{API}/products/{quote(id_produto, safe='')}/items"
        resposta = await self._http.requisitar(
            "GET", url, aceitos=(200, 404), headers={"authorization": f"Bearer {token}"}
        )
        dados = ler_json(resposta) if resposta.status_code == 200 else {}
        brutos = dados.get("results") if isinstance(dados, dict) else None
        itens = [
            i
            for i in brutos or []
            if isinstance(i, dict)
            and i.get("item_id")
            and i.get("currency_id", "BRL") == "BRL"
            and _numero(i.get("price")) > 0
        ]
        # o filtro padrão do site mostra só novos: as mais baratas novas vêm primeiro
        itens.sort(key=lambda i: (i.get("condition") != "new", i["price"]))
        return itens[:OFERTAS_POR_PRODUTO]

    async def _vendedores(self, ids: set[Any], token: str) -> dict[Any, str]:
        ids = {i for i in ids if isinstance(i, int)}
        if not ids:
            return {}
        url = f"{API}/users?ids={','.join(map(str, sorted(ids)))}"
        try:
            resposta = await self._http.requisitar(
                "GET", url, headers={"authorization": f"Bearer {token}"}
            )
            dados = ler_json(resposta)
        except ErroExterno:
            return {}
        nomes = {}
        for entrada in dados if isinstance(dados, list) else []:
            corpo = entrada.get("body", entrada) if isinstance(entrada, dict) else None
            if isinstance(corpo, dict) and isinstance(corpo.get("nickname"), str):
                nomes[corpo.get("id")] = corpo["nickname"]
        return nomes

    def _oferta(
        self,
        produto: dict[str, Any],
        item: dict[str, Any],
        posicao: int,
        ctx: ContextoBusca,
        vendedores: dict[Any, str],
    ) -> Oferta | None:
        if not item.get("price"):
            return None
        info_frete = item.get("shipping") or {}
        if info_frete.get("free_shipping"):
            frete = Frete(StatusFrete.GRATIS_ANUNCIADO, valor=0)
        else:
            frete = ctx.frete_sem_cotacao()
        atributos = {
            a.get("id"): a.get("value_name")
            for a in produto.get("attributes") or []
            if isinstance(a, dict)
        }
        gtins = (g.strip() for g in str(atributos.get("GTIN") or "").split(","))
        fotos = [f.get("url") for f in produto.get("pictures") or [] if isinstance(f, dict)]
        foto = fotos[0] if fotos and isinstance(fotos[0], str) else ""
        titulo = str(produto.get("name") or "")
        usado = item.get("condition") == "used"
        if usado:
            titulo = f"{titulo} (usado)"
        id_item = str(item["item_id"])
        vendedor = vendedores.get(item.get("seller_id"))
        original = item.get("original_price")
        return Oferta(
            id=f"{self.id}:{id_item}",
            titulo=titulo,
            link=f"{SITE}/{id_item[:3]}-{id_item[3:]}-_JM",
            loja=self._ref,
            preco=para_centavos(item["price"]),
            origem=Origem.MARKETPLACE,
            vendedor=vendedor,
            imagem=foto.replace("http://", "https://") or None,
            marca=atributos.get("BRAND"),
            ean=next(filter(None, map(normalizar_ean, gtins)), None),
            condicao=Condicao.USADO if usado else None,
            preco_original=para_centavos(original) if original else None,
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


def _numero(valor: Any) -> float:
    return float(valor) if isinstance(valor, int | float) else 0.0
