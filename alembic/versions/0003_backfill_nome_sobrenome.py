"""BACKFILL: preenche primeiro_nome e sobrenome dos registros antigos.

Fase 2 do padrão Expand-Contract. Roda depois que a aplicação já faz dual write
(grava `cliente` + `primeiro_nome` + `sobrenome`). É idempotente: só toca em
linhas em que os dois campos novos ainda são NULL.

A regra de divisão é copiada de database.dividir_nome de propósito: migrações
não devem importar código da aplicação, que muda com o tempo.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _dividir(nome):
    partes = (nome or "").split()
    if not partes:
        return "", ""
    return partes[0], " ".join(partes[1:])


def upgrade():
    bind = op.get_bind()
    colunas = {c["name"] for c in sa.inspect(bind).get_columns("transacoes")}
    if "cliente" not in colunas:
        return

    linhas = bind.execute(
        sa.text(
            "SELECT id_transacao, cliente FROM transacoes "
            "WHERE primeiro_nome IS NULL AND sobrenome IS NULL"
        )
    ).fetchall()
    for id_transacao, cliente in linhas:
        primeiro, sobrenome = _dividir(cliente)
        bind.execute(
            sa.text(
                "UPDATE transacoes SET primeiro_nome = :p, sobrenome = :s "
                "WHERE id_transacao = :i"
            ),
            {"p": primeiro, "s": sobrenome, "i": id_transacao},
        )


def downgrade():
    # Os dados preenchidos são inofensivos: não há o que desfazer.
    pass
