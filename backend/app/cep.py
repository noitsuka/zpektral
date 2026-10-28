import asyncio
import re
from typing import Any

import httpx

from app.cache import CacheComValidade
from app.cliente_http import ClienteHttp, ErroExterno, ler_json
from app.modelos import Endereco

_NAO_DIGITO = re.compile(r"\D")
TAMANHO_MAXIMO_CAMPO = 120


class CepInvalido(ValueError):
    pass


class CepNaoEncontrado(LookupError):
    pass


def normalizar_cep(bruto: str) -> str:
    digitos = _NAO_DIGITO.sub("", bruto)
    if len(digitos) != 8 or digitos == "00000000":
        raise CepInvalido("CEP inválido: informe os 8 dígitos")
    return digitos


class ServicoCep:
    def __init__(self, http: ClienteHttp, validade: float, entradas_maximas: int):
        self._http = http
        self._cache_ceps: CacheComValidade[str, Endereco] = CacheComValidade(
            validade, entradas_maximas
        )
        self._inexistentes: CacheComValidade[str, bool] = CacheComValidade(600, entradas_maximas)

    async def consultar(self, bruto: str) -> Endereco:
        cep = normalizar_cep(bruto)
        if self._inexistentes.obter(cep):
            raise CepNaoEncontrado(cep)
        try:
            return await self._cache_ceps.obter_ou_carregar(cep, lambda: self._buscar(cep))
        except CepNaoEncontrado:
            self._inexistentes.guardar(cep, True)
            raise

    async def resolver(self, bruto: str) -> Endereco:
        try:
            return await self.consultar(bruto)
        except ErroExterno:
            return Endereco(normalizar_cep(bruto), None, None, None, None)

    async def _buscar(self, cep: str) -> Endereco:
        tarefas = [asyncio.create_task(funcao(cep)) for funcao in (self._brasilapi, self._viacep)]
        nao_achados = 0
        try:
            for proximo in asyncio.as_completed(tarefas):
                try:
                    return await proximo
                except CepNaoEncontrado:
                    nao_achados += 1
                except ErroExterno:
                    pass
        finally:
            for tarefa in tarefas:
                tarefa.cancel()
        if nao_achados == len(tarefas):
            raise CepNaoEncontrado(cep)
        raise ErroExterno("serviços de CEP indisponíveis")

    async def _brasilapi(self, cep: str) -> Endereco:
        resposta = await self._http.requisitar(
            "GET", f"https://brasilapi.com.br/api/cep/v2/{cep}", aceitos=(200, 404)
        )
        if resposta.status_code == 404:
            raise CepNaoEncontrado(cep)
        dados = _objeto(resposta)
        return Endereco(
            cep=cep,
            logradouro=_texto(dados, "street"),
            bairro=_texto(dados, "neighborhood"),
            cidade=_texto(dados, "city"),
            uf=_texto(dados, "state"),
        )

    async def _viacep(self, cep: str) -> Endereco:
        resposta = await self._http.requisitar(
            "GET", f"https://viacep.com.br/ws/{cep}/json/", aceitos=(200, 400)
        )
        if resposta.status_code == 400:
            raise CepNaoEncontrado(cep)
        dados = _objeto(resposta)
        if dados.get("erro"):
            raise CepNaoEncontrado(cep)
        return Endereco(
            cep=cep,
            logradouro=_texto(dados, "logradouro"),
            bairro=_texto(dados, "bairro"),
            cidade=_texto(dados, "localidade"),
            uf=_texto(dados, "uf"),
        )


def _objeto(resposta: httpx.Response) -> dict[str, Any]:
    dados = ler_json(resposta)
    if not isinstance(dados, dict):
        raise ErroExterno("serviço de CEP respondeu num formato inesperado")
    return dados


def _texto(dados: dict[str, Any], chave: str) -> str | None:
    valor = dados.get(chave)
    if not isinstance(valor, str):
        return None
    valor = valor.strip()[:TAMANHO_MAXIMO_CAMPO]
    return valor or None
