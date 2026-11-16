"""CONTRACT: remove a coluna legada `cliente`.

Fase 3 do padrão Expand-Contract. Só deve ser aplicada quando nenhuma versão da
aplicação que leia/grave `cliente` estiver mais em execução (compatibilidade N-1).

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _colunas():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("transacoes")}


def upgrade():
    if "cliente" in _colunas():
        with op.batch_alter_table("transacoes") as batch:
            batch.drop_column("cliente")


def downgrade():
    if "cliente" not in _colunas():
        with op.batch_alter_table("transacoes") as batch:
            batch.add_column(sa.Column("cliente", sa.TEXT, nullable=True))
    op.execute(
        "UPDATE transacoes SET cliente = TRIM(COALESCE(primeiro_nome, '') "
        "|| ' ' || COALESCE(sobrenome, '')) WHERE cliente IS NULL"
    )
