"""Schema inicial (v1): tabela transacoes com a coluna única `cliente`.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Idempotente: se a tabela já existe (criada por database.inicializar_banco),
    # não há nada a fazer.
    if "transacoes" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "transacoes",
        sa.Column("id_transacao", sa.TEXT, primary_key=True),
        sa.Column("cliente", sa.TEXT, nullable=False),
        sa.Column("cpf", sa.TEXT, nullable=False),
        sa.Column("idade", sa.INTEGER),
        sa.Column("valor_bruto", sa.REAL),
        sa.Column("valor_final", sa.REAL),
        sa.Column("status", sa.TEXT),
        sa.Column("motivo_rejeicao", sa.TEXT, nullable=True),
        sa.Column("data_processamento", sa.TIMESTAMP),
    )


def downgrade():
    op.drop_table("transacoes")
