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
