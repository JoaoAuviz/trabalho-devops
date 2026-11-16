"""Camada de persistência SQLite.

`inicializar_banco` cria o schema ATUAL (primeiro_nome + sobrenome, sem `cliente`).
Bancos já existentes evoluem pelo Alembic (padrão Expand-Contract).

`salvar_transacao` é ciente da fase do schema: grava apenas nas colunas que existem.
Assim a mesma versão do código funciona antes do Expand (só `cliente`), durante o
Expand (dual write: `cliente` + `primeiro_nome` + `sobrenome`) e depois do Contract.
"""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "sistema.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS transacoes (
    id_transacao TEXT PRIMARY KEY,
    primeiro_nome TEXT,
    sobrenome TEXT,
    cpf TEXT NOT NULL,
    idade INTEGER,
    valor_bruto REAL,
    valor_final REAL,
    status TEXT,
    motivo_rejeicao TEXT,
    data_processamento TIMESTAMP
)
"""


def conectar(caminho: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dividir_nome(nome_completo: str) -> tuple[str, str]:
    """'Carlos Eduardo Silva' -> ('Carlos', 'Eduardo Silva')."""
    partes = (nome_completo or "").split()
    if not partes:
        return "", ""
    return partes[0], " ".join(partes[1:])


def _colunas(conn: sqlite3.Connection) -> set:
    return {linha[1] for linha in conn.execute("PRAGMA table_info(transacoes)")}


def inicializar_banco(conn: sqlite3.Connection = None) -> None:
    """Cria a estrutura de tabelas se não existirem."""
    propria = conn is None
    if propria:
        conn = conectar()
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        if propria:
            conn.close()


def salvar_transacao(dados: dict, conn: sqlite3.Connection = None) -> None:
    """Insere (ou substitui, para reprocessamento idempotente) o registro processado.

    Aceita `primeiro_nome`/`sobrenome` ou, como entrada legada, `cliente`
    (nome completo). Preenche todas as colunas de nome presentes no schema.
    """
    if "primeiro_nome" in dados or "sobrenome" in dados:
        primeiro = dados.get("primeiro_nome") or ""
        sobrenome = dados.get("sobrenome") or ""
        cliente = f"{primeiro} {sobrenome}".strip()
    else:
        cliente = dados.get("cliente") or ""
        primeiro, sobrenome = dividir_nome(cliente)

    valores = {
        "id_transacao": dados["id_transacao"],
        "cliente": cliente,
        "primeiro_nome": primeiro,
        "sobrenome": sobrenome,
        "cpf": dados["cpf"],
        "idade": dados.get("idade"),
        "valor_bruto": dados.get("valor_bruto"),
        "valor_final": dados.get("valor_final"),
        "status": dados.get("status"),
        "motivo_rejeicao": dados.get("motivo_rejeicao"),
        "data_processamento": dados.get("data_processamento")
        or datetime.now().isoformat(timespec="seconds"),
    }

    propria = conn is None
    if propria:
        conn = conectar()
    try:
        existentes = _colunas(conn)
        # Nomes de coluna vêm do dicionário fixo acima, nunca de entrada externa.
        usar = {k: v for k, v in valores.items() if k in existentes}
        colunas = ", ".join(usar)
        marcas = ", ".join("?" for _ in usar)
        conn.execute(
            f"INSERT OR REPLACE INTO transacoes ({colunas}) VALUES ({marcas})",
            list(usar.values()),
        )
        conn.commit()
    finally:
        if propria:
            conn.close()


def buscar_transacao_por_id(id_transacao: str, conn: sqlite3.Connection = None):
    """Retorna o registro como dict, ou None se não existir."""
    propria = conn is None
    if propria:
        conn = conectar()
    try:
        linha = conn.execute(
            "SELECT * FROM transacoes WHERE id_transacao = ?", (id_transacao,)
        ).fetchone()
    finally:
        if propria:
            conn.close()
    return dict(linha) if linha else None


def backfill_nomes(conn: sqlite3.Connection = None) -> int:
    """Preenche primeiro_nome/sobrenome dos registros antigos a partir de `cliente`.

    Idempotente: só atualiza linhas em que ambos os campos novos ainda são NULL.
    Retorna a quantidade de linhas atualizadas (0 se o schema não tem as colunas).
    """
    propria = conn is None
    if propria:
        conn = conectar()
    try:
        if not {"cliente", "primeiro_nome", "sobrenome"} <= _colunas(conn):
            return 0
        linhas = conn.execute(
            "SELECT id_transacao, cliente FROM transacoes "
            "WHERE primeiro_nome IS NULL AND sobrenome IS NULL"
        ).fetchall()
        for id_transacao, cliente in linhas:
            primeiro, sobrenome = dividir_nome(cliente)
            conn.execute(
                "UPDATE transacoes SET primeiro_nome = ?, sobrenome = ? "
                "WHERE id_transacao = ?",
                (primeiro, sobrenome, id_transacao),
            )
        conn.commit()
        return len(linhas)
    finally:
        if propria:
            conn.close()
