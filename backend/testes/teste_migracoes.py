import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

NOVAS = {"preco_original", "link", "imagem", "consulta", "agendada"}


def _colunas(arquivo: Path) -> set[str]:
    with sqlite3.connect(arquivo) as conexao:
        return {linha[1] for linha in conexao.execute("PRAGMA table_info(historico_precos)")}


def teste_migracao_do_historico_vai_e_volta_sem_perder_linhas(tmp_path):
    arquivo = tmp_path / "migracoes.db"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{arquivo}")

    command.upgrade(config, "0002")
    with sqlite3.connect(arquivo) as conexao:
        conexao.execute(
            "INSERT INTO historico_precos (oferta, loja, titulo, preco, status_frete, total) "
            "VALUES ('a:1', 'a', 'TV', 100, 'sem_cep', 100)"
        )
    command.upgrade(config, "head")
    command.check(config)
    assert _colunas(arquivo) >= NOVAS
    with sqlite3.connect(arquivo) as conexao:
        assert conexao.execute("SELECT agendada, link FROM historico_precos").fetchall() == [
            (0, None)
        ]

    command.downgrade(config, "0002")
    assert not NOVAS & _colunas(arquivo)
    with sqlite3.connect(arquivo) as conexao:
        assert conexao.execute("SELECT count(*) FROM historico_precos").fetchone() == (1,)
    command.upgrade(config, "head")


async def _gravar_uma_busca(url: str, config) -> int:
    from sqlalchemy import func, select

    from app.banco import HistoricoPreco, criar_motor, criar_sessoes
    from app.busca import ServicoBusca
    from app.historico import RegistroHistorico
    from testes.falsos import FonteFalsa

    motor = criar_motor(url)
    sessoes = criar_sessoes(motor)
    registro = RegistroHistorico(sessoes)
    svc = ServicoBusca(
        [FonteFalsa("a", [("Smart TV 55", 1)])], config, ao_concluir=registro.registrar
    )
    trabalho, _ = svc.iniciar("smart tv 55", None)
    await trabalho.gravado.wait()
    async with sessoes() as sessao:
        linhas = await sessao.scalar(select(func.count()).select_from(HistoricoPreco))
    await motor.dispose()
    return linhas if trabalho.historico_gravado else -1


def teste_historico_grava_com_o_banco_na_0003_e_na_0004(tmp_path, config):
    import asyncio

    for versao in ("0003", "0004"):
        arquivo = tmp_path / f"{versao}.db"
        alembic = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        alembic.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{arquivo}")
        command.upgrade(alembic, versao)
        url = f"sqlite+aiosqlite:///{arquivo}"
        assert asyncio.run(_gravar_uma_busca(url, config)) == 1, versao


def teste_migracao_das_credenciais_cria_e_remove_a_tabela(tmp_path):
    arquivo = tmp_path / "credenciais.db"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{arquivo}")

    command.upgrade(config, "head")
    command.check(config)

    def tabelas():
        with sqlite3.connect(arquivo) as conexao:
            return {n for (n,) in conexao.execute("SELECT name FROM sqlite_master")}

    assert "credenciais_oauth" in tabelas()
    command.downgrade(config, "0003")
    assert "credenciais_oauth" not in tabelas()
