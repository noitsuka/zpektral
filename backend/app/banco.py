from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_ESQUEMAS_POSTGRES = {"postgres", "postgresql", "postgresql+asyncpg", "postgresql+psycopg"}
_MODOS_SSL = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}


def url_assincrona(endereco: str) -> str:
    url = make_url(endereco)
    if url.drivername not in _ESQUEMAS_POSTGRES:
        return endereco
    opcoes = dict(url.query)
    modo_ssl = opcoes.pop("sslmode", None)
    for exclusiva_libpq in ("channel_binding", "options", "target_session_attrs"):
        opcoes.pop(exclusiva_libpq, None)
    if modo_ssl in _MODOS_SSL:
        opcoes.setdefault("ssl", modo_ssl)
    return url.set(drivername="postgresql+asyncpg", query=opcoes).render_as_string(
        hide_password=False
    )


class Base(DeclarativeBase):
    pass


IdGrande = BigInteger().with_variant(Integer(), "sqlite")


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id: Mapped[int] = mapped_column(IdGrande, primary_key=True)
    observado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    produto: Mapped[str | None] = mapped_column(String(80))
    oferta: Mapped[str | None] = mapped_column(String(160))
    ean: Mapped[str | None] = mapped_column(String(14), index=True)
    loja: Mapped[str] = mapped_column(String(80))
    vendedor: Mapped[str | None] = mapped_column(String(120))
    prefixo_cep: Mapped[str | None] = mapped_column(String(5))
    titulo: Mapped[str] = mapped_column(String(300))
    preco: Mapped[int] = mapped_column(Integer)
    preco_pix: Mapped[int | None] = mapped_column(Integer)
    frete: Mapped[int | None] = mapped_column(Integer)
    status_frete: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_historico_precos_serie", "produto", "prefixo_cep", "loja", "observado_em"),
        Index("ix_historico_precos_oferta", "oferta", "observado_em"),
    )


class SaudeLoja(Base):
    __tablename__ = "saude_lojas"

    id: Mapped[int] = mapped_column(IdGrande, primary_key=True)
    observado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    loja: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    tempo_decorrido_ms: Mapped[int] = mapped_column(Integer)
    ofertas: Mapped[int] = mapped_column(Integer)
    mensagem: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (Index("ix_saude_lojas_loja_momento", "loja", "observado_em"),)


def criar_motor(url: str) -> AsyncEngine:
    url = url_assincrona(url)
    if url.startswith("sqlite"):
        return create_async_engine(url)
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        connect_args={"timeout": 5, "command_timeout": 10},
    )


async def criar_tabelas_locais(motor: AsyncEngine) -> None:
    if motor.url.get_backend_name() != "sqlite":
        return
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)


def criar_sessoes(motor: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(motor, expire_on_commit=False)
