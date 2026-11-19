import base64
import binascii
import os
import zlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import orjson
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.banco import CredencialOAuth

_TAMANHO_NONCE = 12


def nova_chave() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


class Cifra:
    """AES-GCM com a fonte como dado associado: o registro de uma fonte não abre como de outra."""

    def __init__(self, chave: str):
        try:
            bruta = base64.urlsafe_b64decode(chave.encode())
        except (binascii.Error, ValueError):
            bruta = b""
        if len(bruta) != 32:
            raise ValueError("CHAVE_CREDENCIAIS precisa ter 32 bytes em base64 urlsafe")
        self._aes = AESGCM(bruta)

    def cifrar(self, dados: dict[str, Any], fonte: str) -> str:
        nonce = os.urandom(_TAMANHO_NONCE)
        selado = self._aes.encrypt(nonce, orjson.dumps(dados), fonte.encode())
        return base64.urlsafe_b64encode(nonce + selado).decode()

    def decifrar(self, cifrado: str, fonte: str) -> dict[str, Any] | None:
        try:
            bruto = base64.urlsafe_b64decode(cifrado.encode())
            nonce, selado = bruto[:_TAMANHO_NONCE], bruto[_TAMANHO_NONCE:]
            dados = orjson.loads(self._aes.decrypt(nonce, selado, fonte.encode()))
        except (binascii.Error, ValueError, InvalidTag):
            return None
        return dados if isinstance(dados, dict) else None


@dataclass
class Travada:
    atual: dict[str, Any] | None
    novo: dict[str, Any] | None = None


class GuardaCredenciais:
    """Credenciais OAuth no banco, para valerem em todas as instâncias da API."""

    def __init__(self, sessoes: async_sessionmaker, cifra: Cifra):
        self._sessoes = sessoes
        self._cifra = cifra

    async def ler(self, fonte: str) -> dict[str, Any] | None:
        async with self._sessoes() as sessao:
            cifrado = await sessao.scalar(
                select(CredencialOAuth.dados).where(CredencialOAuth.fonte == fonte)
            )
        return self._cifra.decifrar(cifrado, fonte) if cifrado else None

    @asynccontextmanager
    async def travar(self, fonte: str) -> AsyncIterator[Travada]:
        """Lê a credencial e grava `novo` no fim; uma instância por vez, quando é PostgreSQL."""
        async with self._sessoes() as sessao, sessao.begin():
            if (await sessao.connection()).dialect.name == "postgresql":
                # trava consultiva e não de linha: vale também antes de a linha existir
                chave = zlib.crc32(f"credencial:{fonte}".encode())
                await sessao.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": chave})
            linha = await sessao.get(CredencialOAuth, fonte)
            travada = Travada(self._cifra.decifrar(linha.dados, fonte) if linha else None)
            yield travada
            if travada.novo is None:
                return
            dados = self._cifra.cifrar(travada.novo, fonte)
            if linha is None:
                sessao.add(CredencialOAuth(fonte=fonte, dados=dados))
            else:
                linha.dados = dados
