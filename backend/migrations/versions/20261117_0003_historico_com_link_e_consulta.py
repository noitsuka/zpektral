from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUNAS = ("preco_original", "link", "imagem", "consulta", "agendada")


def upgrade() -> None:
    with op.batch_alter_table("historico_precos") as tabela:
        tabela.add_column(sa.Column("preco_original", sa.Integer()))
        tabela.add_column(sa.Column("link", sa.String(2048)))
        tabela.add_column(sa.Column("imagem", sa.String(2048)))
        tabela.add_column(sa.Column("consulta", sa.String(120)))
        tabela.add_column(
            sa.Column("agendada", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("historico_precos") as tabela:
        for coluna in reversed(COLUNAS):
            tabela.drop_column(coluna)
