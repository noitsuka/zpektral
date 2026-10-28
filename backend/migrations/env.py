import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from app.banco import Base, criar_motor, url_assincrona
from app.configuracao import obter_configuracoes

target_metadata = Base.metadata


def _url() -> str:
    url = context.config.get_main_option("sqlalchemy.url") or obter_configuracoes().url_banco
    if not url:
        raise SystemExit("defina DATABASE_URL para rodar as migrations")
    return url


def migrar_offline() -> None:
    context.configure(
        url=url_assincrona(_url()), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def _executar(conexao: Connection) -> None:
    context.configure(connection=conexao, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrar_online() -> None:
    motor = criar_motor(_url())
    async with motor.connect() as conexao:
        await conexao.run_sync(_executar)
    await motor.dispose()


if context.is_offline_mode():
    migrar_offline()
else:
    asyncio.run(migrar_online())
