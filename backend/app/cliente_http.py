import asyncio
import ipaddress
import random
from collections import defaultdict
from typing import Any

import httpx
import orjson

from app.configuracao import Configuracoes

STATUS_REPETIVEIS = {429, 500, 502, 503, 504}
ESPERA_MAXIMA_RETRY_AFTER = 5.0


def segundos_de_espera(valor: str | None) -> float:
    if not valor:
        return 0.0
    try:
        return min(ESPERA_MAXIMA_RETRY_AFTER, max(0.0, float(valor)))
    except ValueError:
        return 0.0


_CABECALHOS_CORPO = {"content-encoding", "content-length", "transfer-encoding"}


class ErroExterno(Exception):
    pass


class DestinoProibido(httpx.RequestError):
    pass


def _host_interno(host: str) -> bool:
    if host == "localhost" or host.endswith((".localhost", ".internal", ".local")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


async def _exigir_destino_publico(requisicao: httpx.Request) -> None:
    if requisicao.url.scheme != "https" or _host_interno(requisicao.url.host):
        raise DestinoProibido(f"destino recusado: {requisicao.url.host}", request=requisicao)


def criar_cliente(config: Configuracoes) -> httpx.AsyncClient:
    conexoes = config.requisicoes_por_host
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            config.segundos_limite_leitura, connect=config.segundos_limite_conexao
        ),
        limits=httpx.Limits(
            max_connections=conexoes,
            max_keepalive_connections=conexoes,
            keepalive_expiry=60,
        ),
        headers={
            "user-agent": config.agente_usuario,
            "accept": "application/json, text/html;q=0.9",
            "accept-language": "pt-BR,pt;q=0.9",
        },
        follow_redirects=True,
        max_redirects=5,
        event_hooks={"request": [_exigir_destino_publico]},
    )


class ClienteHttp:
    def __init__(self, config: Configuracoes, bytes_maximo: int = 8_000_000):
        self._config = config
        self._bytes_maximo = bytes_maximo
        self._clientes: dict[str, httpx.AsyncClient] = {}
        self._vagas: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.requisicoes_por_host)
        )

    def _cliente(self, host: str) -> httpx.AsyncClient:
        cliente = self._clientes.get(host)
        if cliente is None:
            if len(self._clientes) >= self._config.hosts_maximos:
                raise ErroExterno(f"{host}: limite de hosts atingido")
            cliente = self._clientes[host] = criar_cliente(self._config)
        return cliente

    async def fechar(self) -> None:
        clientes, self._clientes = list(self._clientes.values()), {}
        await asyncio.gather(*(c.aclose() for c in clientes), return_exceptions=True)

    async def __aenter__(self) -> "ClienteHttp":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.fechar()

    async def requisitar(
        self,
        metodo: str,
        url: str,
        *,
        tentativas: int = 1,
        aceitos: tuple[int, ...] = (200,),
        **argumentos: Any,
    ) -> httpx.Response:
        host = httpx.URL(url).host
        tentativa = 0
        espera_pedida = 0.0
        while True:
            try:
                async with self._vagas[host]:
                    resposta = await self._buscar(metodo, url, host, **argumentos)
            except DestinoProibido as excecao:
                raise ErroExterno(str(excecao)) from excecao
            except httpx.HTTPError as excecao:
                if tentativa >= tentativas:
                    raise ErroExterno(f"{host}: {type(excecao).__name__}") from excecao
            else:
                if resposta.status_code in aceitos:
                    return resposta
                if resposta.status_code not in STATUS_REPETIVEIS or tentativa >= tentativas:
                    raise ErroExterno(f"{host}: HTTP {resposta.status_code}")
                espera_pedida = segundos_de_espera(resposta.headers.get("retry-after"))
            tentativa += 1
            await asyncio.sleep(max(espera_pedida, 0.1 * tentativa + random.random() * 0.15))

    async def _buscar(self, metodo: str, url: str, host: str, **argumentos: Any) -> httpx.Response:
        async with self._cliente(host).stream(metodo, url, **argumentos) as resposta:
            declarado = resposta.headers.get("content-length")
            if declarado and declarado.isdigit() and int(declarado) > self._bytes_maximo:
                raise ErroExterno(f"{host}: resposta grande demais")
            corpo = bytearray()
            async for pedaco in resposta.aiter_bytes():
                corpo += pedaco
                if len(corpo) > self._bytes_maximo:
                    raise ErroExterno(f"{host}: resposta grande demais")
            headers = [
                (k, v)
                for k, v in resposta.headers.multi_items()
                if k.lower() not in _CABECALHOS_CORPO
            ]
            return httpx.Response(
                resposta.status_code,
                headers=headers,
                content=bytes(corpo),
                request=resposta.request,
            )

    async def obter_json(self, url: str, **argumentos: Any) -> Any:
        resposta = await self.requisitar("GET", url, **argumentos)
        return ler_json(resposta)

    async def enviar_json(self, url: str, corpo: Any, **argumentos: Any) -> Any:
        resposta = await self.requisitar(
            "POST",
            url,
            content=orjson.dumps(corpo),
            headers={"content-type": "application/json"},
            **argumentos,
        )
        return ler_json(resposta)


def ler_json(resposta: httpx.Response) -> Any:
    try:
        return orjson.loads(resposta.content)
    except orjson.JSONDecodeError:
        try:
            host = resposta.request.url.host
        except RuntimeError:
            host = "loja"
        raise ErroExterno(f"{host}: resposta não é JSON") from None
