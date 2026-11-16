"""EXPAND: adiciona primeiro_nome e sobrenome e torna `cliente` opcional.

Fase 1 do padrão Expand-Contract. Nada é removido: a versão N-1 da aplicação
(que só conhece `cliente`) continua funcionando, desde que `cliente` aceite NULL
para a versão N-1 não quebrar quando a N deixar de preenchê-lo.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _colunas():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("transacoes")}


def upgrade():
    colunas = _colunas()
    with op.batch_alter_table("transacoes") as batch:
        if "primeiro_nome" not in colunas:
            batch.add_column(sa.Column("primeiro_nome", sa.TEXT, nullable=True))
        if "sobrenome" not in colunas:
            batch.add_column(sa.Column("sobrenome", sa.TEXT, nullable=True))
        if "cliente" in colunas:
            batch.alter_column("cliente", existing_type=sa.TEXT, nullable=True)


def downgrade():
    colunas = _colunas()
    if "cliente" in colunas:
        op.execute(
            "UPDATE transacoes SET cliente = TRIM(COALESCE(primeiro_nome, '') "
            "|| ' ' || COALESCE(sobrenome, '')) WHERE cliente IS NULL"
        )
    with op.batch_alter_table("transacoes") as batch:
        if "cliente" in colunas:
            batch.alter_column("cliente", existing_type=sa.TEXT, nullable=False)
        if "primeiro_nome" in colunas:
            batch.drop_column("primeiro_nome")
        if "sobrenome" in colunas:
            batch.drop_column("sobrenome")
