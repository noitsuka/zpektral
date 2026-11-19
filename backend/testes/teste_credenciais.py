import asyncio
import base64
import os

import pytest
from sqlalchemy import select

from app.banco import Base, CredencialOAuth, criar_motor, criar_sessoes
from app.credenciais import Cifra, GuardaCredenciais, nova_chave

URL_PG = os.environ.get("URL_BANCO_TESTE")


async def _motor(url: str):
    motor = criar_motor(url)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
        await conexao.run_sync(Base.metadata.create_all)
    return motor


@pytest.fixture
async def sessoes(tmp_path):
    motor = await _motor(URL_PG or f"sqlite+aiosqlite:///{tmp_path / 'c.db'}")
    yield criar_sessoes(motor)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
    await motor.dispose()


def teste_cifra_vai_e_volta_e_fica_presa_a_fonte():
    cifra = Cifra(nova_chave())
    cifrado = cifra.cifrar({"refresh_token": "TG-segredo"}, "mercadolivre")
    assert "TG-segredo" not in cifrado
    assert cifra.decifrar(cifrado, "mercadolivre") == {"refresh_token": "TG-segredo"}
    assert cifra.cifrar({"a": 1}, "mercadolivre") != cifra.cifrar({"a": 1}, "mercadolivre")
    assert cifra.decifrar(cifrado, "shopee") is None
    assert Cifra(nova_chave()).decifrar(cifrado, "mercadolivre") is None
    assert cifra.decifrar("nao-e-base64!", "mercadolivre") is None
    assert cifra.decifrar("", "mercadolivre") is None


@pytest.mark.parametrize(
    "chave", ["", "curta", base64.urlsafe_b64encode(b"x" * 16).decode(), "%%%%"]
)
def teste_chave_fora_do_formato_e_recusada(chave):
    with pytest.raises(ValueError, match="CHAVE_CREDENCIAIS"):
        Cifra(chave)


async def teste_guarda_grava_cifrado_e_le_de_volta(sessoes):
    guarda = GuardaCredenciais(sessoes, Cifra(nova_chave()))
    assert await guarda.ler("mercadolivre") is None
    async with guarda.travar("mercadolivre") as travada:
        assert travada.atual is None
        travada.novo = {"refresh_token": "TG-1"}
    async with guarda.travar("mercadolivre") as travada:
        assert travada.atual == {"refresh_token": "TG-1"}
        travada.novo = {"refresh_token": "TG-2"}
    assert await guarda.ler("mercadolivre") == {"refresh_token": "TG-2"}
    async with sessoes() as sessao:
        linhas = (await sessao.scalars(select(CredencialOAuth.dados))).all()
    assert len(linhas) == 1 and "TG-2" not in linhas[0]


async def teste_falha_dentro_da_trava_nao_grava(sessoes):
    guarda = GuardaCredenciais(sessoes, Cifra(nova_chave()))
    with pytest.raises(RuntimeError):
        async with guarda.travar("mercadolivre") as travada:
            travada.novo = {"refresh_token": "TG-1"}
            raise RuntimeError("renovação falhou")
    assert await guarda.ler("mercadolivre") is None


async def teste_sem_mudanca_nao_regrava(sessoes):
    guarda = GuardaCredenciais(sessoes, Cifra(nova_chave()))
    async with guarda.travar("mercadolivre") as travada:
        travada.novo = {"refresh_token": "TG-1"}
    async with sessoes() as sessao:
        antes = await sessao.scalar(select(CredencialOAuth.dados))
    async with guarda.travar("mercadolivre"):
        pass
    async with sessoes() as sessao:
        assert await sessao.scalar(select(CredencialOAuth.dados)) == antes


async def teste_chave_trocada_le_como_vazio(sessoes):
    async with GuardaCredenciais(sessoes, Cifra(nova_chave())).travar("ml") as travada:
        travada.novo = {"refresh_token": "TG-1"}
    outra = GuardaCredenciais(sessoes, Cifra(nova_chave()))
    assert await outra.ler("ml") is None
    async with outra.travar("ml") as travada:
        assert travada.atual is None
        travada.novo = {"refresh_token": "TG-9"}
    assert await outra.ler("ml") == {"refresh_token": "TG-9"}


@pytest.mark.skipif(not URL_PG, reason="a trava entre instâncias é do PostgreSQL")
async def teste_trava_do_postgres_serializa_instancias():
    chave = nova_chave()
    motores = [await _motor(URL_PG), criar_motor(URL_PG)]
    guardas = [GuardaCredenciais(criar_sessoes(m), Cifra(chave)) for m in motores]
    ordem: list[str] = []

    async def instancia(nome: str, guarda: GuardaCredenciais):
        async with guarda.travar("mercadolivre") as travada:
            ordem.append(f"{nome} leu {travada.atual}")
            await asyncio.sleep(0.2)
            travada.novo = {"refresh_token": nome}
            ordem.append(f"{nome} saiu")

    try:
        await asyncio.gather(instancia("a", guardas[0]), instancia("b", guardas[1]))
    finally:
        for motor in motores:
            await motor.dispose()
    primeira = ordem[0].split()[0]
    segunda = "b" if primeira == "a" else "a"
    assert ordem == [
        f"{primeira} leu None",
        f"{primeira} saiu",
        f"{segunda} leu {{'refresh_token': '{primeira}'}}",
        f"{segunda} saiu",
    ]
