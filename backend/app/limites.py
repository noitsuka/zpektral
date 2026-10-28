import ipaddress
import math
import time
from collections import OrderedDict

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.configuracao import Configuracoes


class LimitadorTaxa:
    def __init__(self, por_minuto: float, rajada: int, chaves_maximas: int = 100_000, relogio=None):
        self.taxa = por_minuto / 60
        self.rajada = rajada
        self.chaves_maximas = chaves_maximas
        self._relogio = relogio or time.monotonic
        self._baldes: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def consumir(self, chave: str) -> float:
        agora = self._relogio()
        fichas, ultimo = self._baldes.pop(chave, (float(self.rajada), agora))
        fichas = min(self.rajada, fichas + (agora - ultimo) * self.taxa)
        espera = 0.0
        if fichas >= 1:
            fichas -= 1
        else:
            espera = (1 - fichas) / self.taxa
        self._baldes[chave] = (fichas, agora)
        while len(self._baldes) > self.chaves_maximas:
            self._baldes.popitem(last=False)
        return espera


def chave_do_endereco(bruto: str) -> str:
    try:
        ip = ipaddress.ip_address(bruto.strip())
    except ValueError:
        return bruto.strip()[:64] or "desconhecido"
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


def ip_do_cliente(requisicao: Request, confiar_proxy: bool) -> str:
    if confiar_proxy:
        encaminhado = requisicao.headers.get("x-forwarded-for", "")
        saltos = [s.strip() for s in encaminhado.split(",") if s.strip()]
        if saltos:
            return chave_do_endereco(saltos[-1])
    return chave_do_endereco(requisicao.client.host if requisicao.client else "")


def tentar_depois(segundos: float) -> str:
    return str(max(1, math.ceil(segundos)))


CABECALHOS_SEGURANCA_PADRAO = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
CSP_DA_API = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


class CabecalhosSeguranca:
    def __init__(self, app: ASGIApp, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, escopo: Scope, receive: Receive, send: Send) -> None:
        if escopo["type"] != "http":
            await self.app(escopo, receive, send)
            return
        eh_documentacao = escopo["path"] in ("/docs", "/redoc", "/docs/oauth2-redirect")

        async def com_cabecalhos(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                headers = list(mensagem.get("headers", []))
                headers.extend(CABECALHOS_SEGURANCA_PADRAO)
                if not eh_documentacao:
                    headers.append(CSP_DA_API)
                if self.hsts:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                mensagem["headers"] = headers
            await send(mensagem)

        await self.app(escopo, receive, com_cabecalhos)


class Vaga:
    def __init__(self, guarda: "Guarda", ip: str):
        self._guarda = guarda
        self._ip = ip
        self._aberta = True

    def liberar(self) -> None:
        if self._aberta:
            self._aberta = False
            self._guarda.fechar_transmissao(self._ip)


class Limitado(Exception):
    def __init__(self, mensagem: str, espera: float, status: int = 429):
        self.mensagem = mensagem
        self.espera = espera
        self.status = status


class Guarda:
    def __init__(
        self,
        *,
        por_minuto: float,
        rajada: int,
        novas_por_minuto: float,
        rajada_novas: int,
        maximo_em_andamento: int,
        transmissoes_por_ip: int,
        confiar_proxy: bool,
    ):
        self.requisicoes = LimitadorTaxa(por_minuto, rajada)
        self.novas = LimitadorTaxa(novas_por_minuto, rajada_novas)
        self.maximo_em_andamento = maximo_em_andamento
        self.transmissoes_por_ip = transmissoes_por_ip
        self.confiar_proxy = confiar_proxy
        self.transmissoes: dict[str, int] = {}

    @classmethod
    def das_configuracoes(cls, config: Configuracoes) -> "Guarda":
        return cls(
            por_minuto=config.requisicoes_por_minuto,
            rajada=config.rajada_requisicoes,
            novas_por_minuto=config.buscas_novas_por_minuto,
            rajada_novas=config.rajada_buscas_novas,
            maximo_em_andamento=config.maximo_buscas_em_andamento,
            transmissoes_por_ip=config.transmissoes_por_ip,
            confiar_proxy=config.confiar_proxy,
        )

    def ip(self, requisicao: Request) -> str:
        return ip_do_cliente(requisicao, self.confiar_proxy)

    def registrar(self, requisicao: Request) -> None:
        espera = self.requisicoes.consumir(self.ip(requisicao))
        if espera:
            raise Limitado("Muitas requisições. Tente de novo em instantes.", espera)

    def verificar_busca_nova(self, requisicao: Request, em_andamento: int) -> None:
        if em_andamento >= self.maximo_em_andamento:
            raise Limitado("Muitas buscas em andamento. Tente de novo em instantes.", 5, 503)
        espera = self.novas.consumir(self.ip(requisicao))
        if espera:
            raise Limitado("Muitas buscas novas seguidas. Tente de novo em instantes.", espera)

    def abrir_transmissao(self, ip: str) -> Vaga:
        if self.transmissoes.get(ip, 0) >= self.transmissoes_por_ip:
            raise Limitado("Muitas buscas abertas ao mesmo tempo.", 5)
        self.transmissoes[ip] = self.transmissoes.get(ip, 0) + 1
        return Vaga(self, ip)

    def fechar_transmissao(self, ip: str) -> None:
        restante = self.transmissoes.get(ip, 1) - 1
        if restante > 0:
            self.transmissoes[ip] = restante
        else:
            self.transmissoes.pop(ip, None)
