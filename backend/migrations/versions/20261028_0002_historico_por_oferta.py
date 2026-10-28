from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("historico_precos") as tabela:
        tabela.add_column(sa.Column("oferta", sa.String(160)))
        tabela.alter_column("produto", existing_type=sa.String(80), nullable=True)
    op.create_index("ix_historico_precos_oferta", "historico_precos", ["oferta", "observado_em"])


def downgrade() -> None:
    op.drop_index("ix_historico_precos_oferta", table_name="historico_precos")
    op.execute("DELETE FROM historico_precos WHERE produto IS NULL")
    with op.batch_alter_table("historico_precos") as tabela:
        tabela.alter_column("produto", existing_type=sa.String(80), nullable=False)
        tabela.drop_column("oferta")
