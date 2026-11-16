"""Ambiente do Alembic para o banco SQLite do projeto."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Sem modelos ORM: as migrações são escritas à mão.
target_metadata = None


def _url() -> str:
    return "sqlite:///" + os.environ.get("DB_PATH", "sistema.db")


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        # render_as_batch: SQLite não altera colunas com ALTER TABLE;
        # o modo batch recria a tabela de forma segura quando necessário.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError(
        "Modo offline (--sql) não é suportado: as migrações inspecionam o banco."
    )

run_migrations_online()
