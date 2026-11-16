"""Lógica pura de negócio: validação e cálculo de descontos (sem acesso a banco)."""

IDADE_MINIMA = 0
IDADE_MAXIMA = 120
IDADE_IDOSO = 60
IDADE_MAIORIDADE = 18
TAMANHO_CPF = 11

DESCONTO_IDOSO = 0.15
DESCONTO_LIVROS = 0.10
DESCONTO_MAXIMO = 0.25


def validar_transacao(transacao: dict) -> tuple[bool, str]:
    """Valida valor_bruto, idade e cpf. Retorna (True, "OK") ou (False, motivo)."""
    valor = transacao.get("valor_bruto")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor <= 0:
        return False, "valor_bruto deve ser maior que 0"

    idade = transacao.get("idade")
    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or idade < IDADE_MINIMA
        or idade > IDADE_MAXIMA
    ):
        return False, f"idade deve estar entre {IDADE_MINIMA} e {IDADE_MAXIMA}"

    cpf = transacao.get("cpf")
    if (
        not isinstance(cpf, str)
        or len(cpf) != TAMANHO_CPF
        or not (cpf.isascii() and cpf.isdigit())  # isdigit() sozinho aceita "²"
    ):
        return False, "cpf deve ter exatamente 11 dígitos numéricos"

    return True, "OK"


def calcular_desconto_e_final(
    valor_bruto: float, idade: int, categoria: str
) -> tuple[float, float]:
    """Calcula (valor_desconto, valor_final).

    - Menores de 18 anos não podem comprar 'eletronicos' (ValueError).
    - Idosos (>= 60) têm 15% de desconto; categoria 'livros' tem 10%.
    - Descontos são acumulativos, limitados a 25%.
    """
    if idade < IDADE_MAIORIDADE and categoria == "eletronicos":
        raise ValueError("menores de 18 anos não podem comprar eletronicos")

    percentual = 0.0
    if idade >= IDADE_IDOSO:
        percentual += DESCONTO_IDOSO
    if categoria == "livros":
        percentual += DESCONTO_LIVROS
    percentual = min(percentual, DESCONTO_MAXIMO)

    desconto = round(valor_bruto * percentual, 2)
    final = round(valor_bruto - desconto, 2)
    return desconto, final
