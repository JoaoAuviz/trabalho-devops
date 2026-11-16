# Processamento em Lote de Transações — DevOps (Integração e Entrega Contínua)

CLI em Python 3.10+ que valida e processa transações (`dados_processamento.json`),
persiste em SQLite e demonstra as práticas de DevOps da disciplina: testes com
pytest, migrações Alembic (Expand-Contract), CI/CD com GitHub Actions e
observabilidade com logs.

## Estrutura

```
.github/workflows/ci.yml     Esteira CI/CD
alembic/                     Migrações (0001 a 0004)
tests/test_regra_negocio.py  Testes unitários
tests/test_database.py       Testes de integração (SQLite em memória)
dados_processamento.json     10 casos de entrada
regra_negocio.py             Lógica pura (validação e descontos)
database.py                  Persistência SQLite
main.py                      CLI + logging + métricas de tempo
requirements.txt             Dependências
app.log                      Log de execução (gerado)
```

## Como executar

```bash
pip install -r requirements.txt
alembic upgrade head      # aplica as migrações em sistema.db
python main.py            # processa o lote, gera app.log e imprime o sumário
pytest -v                 # roda os testes
flake8 .                  # linter
```

A variável `DB_PATH` troca o arquivo do banco (padrão: `sistema.db`).

## Regras de negócio

| Regra | Detalhe |
|---|---|
| Validação | `valor_bruto > 0`, `idade` entre 0 e 120, `cpf` com exatamente 11 dígitos |
| Menores de 18 | Não podem comprar `eletronicos` (a transação é rejeitada) |
| Idosos (>= 60) | 15% de desconto |
| Categoria `livros` | 10% de desconto |
| Acúmulo | Descontos somam, com teto de 25% |

Resultado esperado para os 10 casos: **7 aprovados e 3 rejeitados**
(TX1005 valor negativo, TX1006 CPF curto, TX1008 valor zero).

## Testes (pirâmide)

- **Unitários:** particionamento de equivalência e análise de valores-limite
  (idade 17/18, 59/60, 0/120; valor 0; CPF com 10/11/12 dígitos).
- **Integração:** inserir, consultar, reprocessar e simular cada fase do schema
  no SQLite em memória.

## Database DevOps: Expand-Contract

Divisão de `cliente` em `primeiro_nome` e `sobrenome` sem parar a aplicação:

| Migração | Fase | O que faz |
|---|---|---|
| `0001` | Base | Schema v1 com `cliente NOT NULL` |
| `0002` | **Expand** | Adiciona `primeiro_nome` e `sobrenome`; `cliente` passa a aceitar NULL |
| `0003` | **Backfill** | Preenche os novos campos dos registros antigos (idempotente) |
| `0004` | **Contract** | Remove a coluna legada `cliente` |

O `salvar_transacao` detecta as colunas existentes e grava só nelas. A mesma
versão do código funciona antes do Expand, durante o dual write e após o
Contract (compatibilidade N-1).

## CI/CD (GitHub Actions)

`ci.yml` roda em todo `push` e `pull_request` no `main`: Python 3.10, instala
dependências, `flake8`, `pytest`, `alembic upgrade head`, executa `main.py` e
publica o `app.log` como artefato.

## Observabilidade

`app.log` e console, formato `data | NÍVEL | mensagem`:

- **INFO:** início e fim do lote (com tempo em ms) e cada transação aprovada.
- **WARNING:** cada transação rejeitada, com o motivo.
- **ERROR:** falha ao ler o JSON ou exceção inesperada (o lote continua).

O sumário final mostra total, aprovados, rejeitados, erros e tempo total em ms
(medido com `time.perf_counter()`).

## Integrantes

<João Gabriel Alves Lima>
