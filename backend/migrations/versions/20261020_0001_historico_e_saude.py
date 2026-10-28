from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IdGrande = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _observado_em() -> sa.Column:
    return sa.Column(
        "observado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "historico_precos",
        sa.Column("id", IdGrande, primary_key=True),
        _observado_em(),
        sa.Column("produto", sa.String(80), nullable=False),
        sa.Column("ean", sa.String(14)),
        sa.Column("loja", sa.String(80), nullable=False),
        sa.Column("vendedor", sa.String(120)),
        sa.Column("prefixo_cep", sa.String(5)),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("preco", sa.Integer(), nullable=False),
        sa.Column("preco_pix", sa.Integer()),
        sa.Column("frete", sa.Integer()),
        sa.Column("status_frete", sa.String(20), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
    )
    op.create_index("ix_historico_precos_ean", "historico_precos", ["ean"])
    op.create_index("ix_historico_precos_observado_em", "historico_precos", ["observado_em"])
    op.create_index(
        "ix_historico_precos_serie",
        "historico_precos",
        ["produto", "prefixo_cep", "loja", "observado_em"],
    )

    op.create_table(
        "saude_lojas",
        sa.Column("id", IdGrande, primary_key=True),
        _observado_em(),
        sa.Column("loja", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tempo_decorrido_ms", sa.Integer(), nullable=False),
        sa.Column("ofertas", sa.Integer(), nullable=False),
        sa.Column("mensagem", sa.String(200)),
    )
    op.create_index("ix_saude_lojas_loja_momento", "saude_lojas", ["loja", "observado_em"])


def downgrade() -> None:
    op.drop_table("saude_lojas")
    op.drop_table("historico_precos")
