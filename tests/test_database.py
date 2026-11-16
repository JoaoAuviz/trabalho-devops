"""Testes de integração: database.py (SQLite em memória) e o fluxo do main.py."""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import main

RAIZ = Path(__file__).resolve().parent.parent

SCHEMA_V1 = """
CREATE TABLE transacoes (
    id_transacao TEXT PRIMARY KEY,
    cliente TEXT NOT NULL,
    cpf TEXT NOT NULL,
    idade INTEGER,
    valor_bruto REAL,
    valor_final REAL,
    status TEXT,
    motivo_rejeicao TEXT,
    data_processamento TIMESTAMP
)
"""

SCHEMA_EXPAND = """
CREATE TABLE transacoes (
    id_transacao TEXT PRIMARY KEY,
    cliente TEXT,
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


def registro(**alteracoes):
    base = {
        "id_transacao": "TX9001",
        "cliente": "Carlos Eduardo Silva",
        "cpf": "12345678901",
        "idade": 25,
        "valor_bruto": 150.0,
        "valor_final": 150.0,
        "status": "APROVADO",
        "motivo_rejeicao": None,
    }
    base.update(alteracoes)
    return base


def carregar_lote():
    caminho = RAIZ / "dados_processamento.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    database.inicializar_banco(c)
    yield c
    c.close()


def conexao_com_schema(ddl):
    c = database.conectar(":memory:")
    c.execute(ddl)
    c.commit()
    return c


# --------------------------------------------------------------------------
# inicializar / salvar / buscar
# --------------------------------------------------------------------------
def test_inicializar_cria_tabela_com_colunas_esperadas(conn):
    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(transacoes)")}
    assert colunas == {
        "id_transacao", "primeiro_nome", "sobrenome", "cpf", "idade",
        "valor_bruto", "valor_final", "status", "motivo_rejeicao",
        "data_processamento",
    }


def test_inicializar_eh_idempotente(conn):
    database.salvar_transacao(registro(), conn)
    database.inicializar_banco(conn)  # segunda chamada não pode apagar nada
    assert database.buscar_transacao_por_id("TX9001", conn) is not None


def test_salvar_e_buscar_transacao_aprovada(conn):
    database.salvar_transacao(registro(), conn)
    salvo = database.buscar_transacao_por_id("TX9001", conn)
    assert salvo["primeiro_nome"] == "Carlos"
    assert salvo["sobrenome"] == "Eduardo Silva"
    assert salvo["cpf"] == "12345678901"
    assert salvo["idade"] == 25
    assert salvo["valor_bruto"] == pytest.approx(150.0)
    assert salvo["valor_final"] == pytest.approx(150.0)
    assert salvo["status"] == "APROVADO"
    assert salvo["motivo_rejeicao"] is None
    assert salvo["data_processamento"]


def test_salvar_e_buscar_transacao_rejeitada(conn):
    rejeitada = registro(
        id_transacao="TX9002",
        status="REJEITADO",
        valor_final=None,
        motivo_rejeicao="cpf deve ter exatamente 11 dígitos numéricos",
    )
    database.salvar_transacao(rejeitada, conn)
    salvo = database.buscar_transacao_por_id("TX9002", conn)
    assert salvo["status"] == "REJEITADO"
    assert salvo["valor_final"] is None
    assert "cpf" in salvo["motivo_rejeicao"]


def test_buscar_id_inexistente_retorna_none(conn):
    assert database.buscar_transacao_por_id("NAO_EXISTE", conn) is None


def test_salvar_mesmo_id_substitui_registro(conn):
    database.salvar_transacao(registro(valor_final=150.0), conn)
    database.salvar_transacao(registro(valor_final=99.0), conn)
    total = conn.execute("SELECT COUNT(*) FROM transacoes").fetchone()[0]
    assert total == 1
    assert database.buscar_transacao_por_id("TX9001", conn)["valor_final"] == 99.0


def test_cpf_e_obrigatorio_no_schema(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO transacoes (id_transacao) VALUES ('SEM_CPF')")


def test_funcoes_abrem_e_fecham_a_propria_conexao(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "teste.db"))
    database.inicializar_banco()
    database.salvar_transacao(registro())
    assert database.buscar_transacao_por_id("TX9001")["status"] == "APROVADO"
    assert database.backfill_nomes() == 0


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("Carlos Eduardo Silva", ("Carlos", "Eduardo Silva")),
        ("Ana Souza", ("Ana", "Souza")),
        ("Madonna", ("Madonna", "")),
        ("  Gabriel   Martins  ", ("Gabriel", "Martins")),
        ("", ("", "")),
        (None, ("", "")),
    ],
)
def test_dividir_nome(nome, esperado):
    assert database.dividir_nome(nome) == esperado


# --------------------------------------------------------------------------
# Expand-Contract: o mesmo código em cada fase do schema (compatibilidade N-1)
# --------------------------------------------------------------------------
def test_fase_v1_grava_apenas_cliente():
    c = conexao_com_schema(SCHEMA_V1)
    database.salvar_transacao(registro(), c)
    salvo = database.buscar_transacao_por_id("TX9001", c)
    assert salvo["cliente"] == "Carlos Eduardo Silva"
    assert "primeiro_nome" not in salvo
    c.close()


def test_fase_expand_faz_dual_write():
    c = conexao_com_schema(SCHEMA_EXPAND)
    database.salvar_transacao(registro(), c)
    salvo = database.buscar_transacao_por_id("TX9001", c)
    assert salvo["cliente"] == "Carlos Eduardo Silva"  # campo legado
    assert salvo["primeiro_nome"] == "Carlos"          # campos novos
    assert salvo["sobrenome"] == "Eduardo Silva"
    c.close()


def test_dual_write_aceita_entrada_ja_dividida():
    c = conexao_com_schema(SCHEMA_EXPAND)
    entrada = registro(primeiro_nome="Ana", sobrenome="Maria Souza")
    del entrada["cliente"]
    database.salvar_transacao(entrada, c)
    salvo = database.buscar_transacao_por_id("TX9001", c)
    assert salvo["cliente"] == "Ana Maria Souza"
    assert (salvo["primeiro_nome"], salvo["sobrenome"]) == ("Ana", "Maria Souza")
    c.close()


def test_fase_contract_nao_tem_coluna_cliente(conn):
    database.salvar_transacao(registro(), conn)
    assert "cliente" not in database.buscar_transacao_por_id("TX9001", conn)


def test_backfill_preenche_registros_antigos():
    c = conexao_com_schema(SCHEMA_V1)
    antigos = [
        ("TX1", "Carlos Eduardo Silva"),
        ("TX2", "Madonna"),
        ("TX3", "Ana Maria Souza"),
    ]
    for id_transacao, cliente in antigos:
        c.execute(
            "INSERT INTO transacoes (id_transacao, cliente, cpf) VALUES (?, ?, '1')",
            (id_transacao, cliente),
        )
    # EXPAND aplicado sobre dados que já existiam
    c.execute("ALTER TABLE transacoes ADD COLUMN primeiro_nome TEXT")
    c.execute("ALTER TABLE transacoes ADD COLUMN sobrenome TEXT")
    # registro novo gravado já com dual write não pode ser sobrescrito
    database.salvar_transacao(registro(id_transacao="TX4", cliente="Novo Cliente"), c)

    assert database.backfill_nomes(c) == 3

    nomes = {
        r["id_transacao"]: (r["primeiro_nome"], r["sobrenome"])
        for r in c.execute("SELECT * FROM transacoes")
    }
    assert nomes["TX1"] == ("Carlos", "Eduardo Silva")
    assert nomes["TX2"] == ("Madonna", "")
    assert nomes["TX3"] == ("Ana", "Maria Souza")
    assert nomes["TX4"] == ("Novo", "Cliente")
    assert database.backfill_nomes(c) == 0  # idempotente
    c.close()


def test_backfill_sem_colunas_novas_nao_faz_nada():
    c = conexao_com_schema(SCHEMA_V1)
    assert database.backfill_nomes(c) == 0
    c.close()


# --------------------------------------------------------------------------
# Fluxo do lote (main.py) sobre os 10 casos do JSON
# --------------------------------------------------------------------------
REJEITADOS = {"TX1005", "TX1006", "TX1008"}


def test_lote_completo_do_json(conn):
    resultados = {
        tx["id_transacao"]: main.processar_transacao(tx, conn) for tx in carregar_lote()
    }
    assert len(resultados) == 10
    for id_transacao, status in resultados.items():
        esperado = "REJEITADO" if id_transacao in REJEITADOS else "APROVADO"
        assert status == esperado, id_transacao

    assert database.buscar_transacao_por_id("TX1003", conn)["valor_final"] == (
        pytest.approx(425.0)
    )
    assert database.buscar_transacao_por_id("TX1002", conn)["valor_final"] == (
        pytest.approx(72.0)
    )
    assert "valor_bruto" in database.buscar_transacao_por_id("TX1005", conn)["motivo_rejeicao"]
    assert "cpf" in database.buscar_transacao_por_id("TX1006", conn)["motivo_rejeicao"]
    assert "valor_bruto" in database.buscar_transacao_por_id("TX1008", conn)["motivo_rejeicao"]
    assert database.buscar_transacao_por_id("TX1005", conn)["valor_final"] is None


def test_menor_comprando_eletronicos_eh_rejeitado(conn):
    tx = {
        "id_transacao": "TX9100", "cliente": "Menor De Idade", "cpf": "12345678901",
        "idade": 17, "valor_bruto": 100.0, "categoria": "eletronicos",
    }
    assert main.processar_transacao(tx, conn) == "REJEITADO"
    salvo = database.buscar_transacao_por_id("TX9100", conn)
    assert salvo["status"] == "REJEITADO"
    assert "eletronicos" in salvo["motivo_rejeicao"]


@pytest.fixture
def ambiente_main(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ARQUIVO_ENTRADA", str(RAIZ / "dados_processamento.json"))
    monkeypatch.setattr(main, "ARQUIVO_LOG", str(tmp_path / "app.log"))
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "sistema.db"))
    yield tmp_path
    for handler in list(main.logger.handlers):
        handler.close()
        main.logger.removeHandler(handler)


def test_main_ponta_a_ponta(ambiente_main, capsys):
    assert main.main() == 0

    saida = capsys.readouterr().out
    assert "Total processado : 10" in saida
    assert "Aprovados        : 7" in saida
    assert "Rejeitados       : 3" in saida
    assert "Tempo total" in saida and "ms" in saida

    log = (ambiente_main / "app.log").read_text(encoding="utf-8")
    assert "Início do processamento" in log
    assert "Fim do processamento" in log
    assert log.count("| INFO") == 9      # início + 7 aprovadas + fim
    assert log.count("| WARNING") == 3   # 3 rejeitadas
    assert "TX1005 REJEITADA" in log

    banco = sqlite3.connect(ambiente_main / "sistema.db")
    assert banco.execute("SELECT COUNT(*) FROM transacoes").fetchone()[0] == 10
    banco.close()


def test_main_reprocessamento_eh_idempotente(ambiente_main):
    assert main.main() == 0
    assert main.main() == 0
    banco = sqlite3.connect(ambiente_main / "sistema.db")
    assert banco.execute("SELECT COUNT(*) FROM transacoes").fetchone()[0] == 10
    banco.close()


def test_main_arquivo_de_entrada_ausente_registra_erro(ambiente_main, monkeypatch):
    monkeypatch.setattr(main, "ARQUIVO_ENTRADA", str(ambiente_main / "nao_existe.json"))
    assert main.main() == 1
    log = (ambiente_main / "app.log").read_text(encoding="utf-8")
    assert "| ERROR" in log
    assert "Falha ao carregar" in log


def test_main_erro_inesperado_nao_derruba_o_lote(ambiente_main, monkeypatch, capsys):
    def falha(*args, **kwargs):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(main.database, "salvar_transacao", falha)
    assert main.main() == 1
    assert "Erros            : 10" in capsys.readouterr().out
    log = (ambiente_main / "app.log").read_text(encoding="utf-8")
    assert log.count("| ERROR") == 10
    assert "Erro inesperado" in log
