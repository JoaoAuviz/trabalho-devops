"""Ponto de entrada CLI: processa o lote de transações com logs e métricas."""
import json
import logging
import sys
import time

import database
from regra_negocio import calcular_desconto_e_final, validar_transacao

ARQUIVO_ENTRADA = "dados_processamento.json"
ARQUIVO_LOG = "app.log"

logger = logging.getLogger("processamento")


def configurar_log() -> None:
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    for handler in (logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formato)
        logger.addHandler(handler)


def processar_transacao(tx: dict, conn) -> str:
    """Processa uma transação e devolve 'APROVADO' ou 'REJEITADO'."""
    registro = dict(tx)
    valido, motivo = validar_transacao(tx)

    if valido:
        try:
            desconto, final = calcular_desconto_e_final(
                tx["valor_bruto"], tx["idade"], tx["categoria"]
            )
        except ValueError as exc:
            valido, motivo = False, str(exc)

    if valido:
        registro.update(valor_final=final, status="APROVADO", motivo_rejeicao=None)
        database.salvar_transacao(registro, conn)
        logger.info(
            "Transação %s APROVADA: bruto=%.2f desconto=%.2f final=%.2f",
            tx["id_transacao"], tx["valor_bruto"], desconto, final,
        )
        return "APROVADO"

    registro.update(valor_final=None, status="REJEITADO", motivo_rejeicao=motivo)
    database.salvar_transacao(registro, conn)
    logger.warning("Transação %s REJEITADA: %s", tx["id_transacao"], motivo)
    return "REJEITADO"


def main() -> int:
    configurar_log()
    logger.info("Início do processamento em lote")
    inicio = time.perf_counter()

    try:
        with open(ARQUIVO_ENTRADA, encoding="utf-8") as f:
            transacoes = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Falha ao carregar %s: %s", ARQUIVO_ENTRADA, exc)
        return 1

    conn = database.conectar()
    database.inicializar_banco(conn)

    contagem = {"APROVADO": 0, "REJEITADO": 0}
    erros = 0
    for tx in transacoes:
        try:
            contagem[processar_transacao(tx, conn)] += 1
        except Exception:  # erro operacional inesperado não derruba o lote
            erros += 1
            logger.exception("Erro inesperado na transação %s", tx.get("id_transacao"))
    conn.close()

    ms = (time.perf_counter() - inicio) * 1000
    logger.info("Fim do processamento em %.2f ms", ms)

    print("\n===== SUMÁRIO =====")
    print(f"Total processado : {len(transacoes)}")
    print(f"Aprovados        : {contagem['APROVADO']}")
    print(f"Rejeitados       : {contagem['REJEITADO']}")
    print(f"Erros            : {erros}")
    print(f"Tempo total      : {ms:.2f} ms")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
