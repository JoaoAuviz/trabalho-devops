"""Testes unitários de regra_negocio.py.

Técnicas aplicadas:
- Particionamento de Equivalência (classes válidas e inválidas por campo);
- Análise de Valores-Limite (0/0,01 no valor; -1/0/120/121 na idade;
  17/18 na maioridade; 59/60 no desconto de idoso; 10/11/12 dígitos no CPF).
"""
import json
from pathlib import Path

import pytest

import regra_negocio
from regra_negocio import calcular_desconto_e_final, validar_transacao

RAIZ = Path(__file__).resolve().parent.parent


def tx_valida(**alteracoes):
    base = {
        "id_transacao": "TX0001",
        "cliente": "Fulano de Tal",
        "cpf": "12345678901",
        "idade": 30,
        "valor_bruto": 100.0,
        "categoria": "vestuario",
    }
    base.update(alteracoes)
    return base


def carregar_json():
    caminho = RAIZ / "dados_processamento.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# validar_transacao
# --------------------------------------------------------------------------
class TestValidarTransacao:
    def test_transacao_valida(self):
        assert validar_transacao(tx_valida()) == (True, "OK")

    # valor_bruto -----------------------------------------------------------
    @pytest.mark.parametrize("valor", [0.01, 1, 150.0, 1_000_000.0])
    def test_valor_positivo_eh_valido(self, valor):
        assert validar_transacao(tx_valida(valor_bruto=valor)) == (True, "OK")

    @pytest.mark.parametrize("valor", [0, 0.0, -0.01, -50.0])
    def test_valor_nao_positivo_eh_invalido(self, valor):
        ok, motivo = validar_transacao(tx_valida(valor_bruto=valor))
        assert ok is False
        assert "valor_bruto" in motivo

    @pytest.mark.parametrize("valor", [None, "100", True, [100]])
    def test_valor_de_tipo_invalido(self, valor):
        ok, motivo = validar_transacao(tx_valida(valor_bruto=valor))
        assert ok is False
        assert "valor_bruto" in motivo

    def test_valor_ausente(self):
        transacao = tx_valida()
        del transacao["valor_bruto"]
        assert validar_transacao(transacao)[0] is False

    # idade -----------------------------------------------------------------
    @pytest.mark.parametrize("idade", [0, 1, 17, 18, 59, 60, 119, 120])
    def test_idade_dentro_do_intervalo_eh_valida(self, idade):
        assert validar_transacao(tx_valida(idade=idade)) == (True, "OK")

    @pytest.mark.parametrize("idade", [-1, 121, 200])
    def test_idade_fora_do_intervalo_eh_invalida(self, idade):
        ok, motivo = validar_transacao(tx_valida(idade=idade))
        assert ok is False
        assert "idade" in motivo

    @pytest.mark.parametrize("idade", [None, "30", 30.5, True])
    def test_idade_de_tipo_invalido(self, idade):
        ok, motivo = validar_transacao(tx_valida(idade=idade))
        assert ok is False
        assert "idade" in motivo

    # cpf -------------------------------------------------------------------
    @pytest.mark.parametrize("cpf", ["12345678901", "00000000000"])
    def test_cpf_com_11_digitos_eh_valido(self, cpf):
        assert validar_transacao(tx_valida(cpf=cpf)) == (True, "OK")

    @pytest.mark.parametrize(
        "cpf",
        [
            "",              # vazio
            "123",           # curto (caso TX1006 do JSON)
            "1234567890",    # 10 dígitos (limite - 1)
            "123456789012",  # 12 dígitos (limite + 1)
            "1234567890a",   # letra
            "123.456.789-01",  # pontuação
            " 2345678901",   # espaço
            "1234567890²",   # dígito Unicode que não é 0-9
            "١٢٣٤٥٦٧٨٩٠١",   # dígitos arábico-índicos
        ],
    )
    def test_cpf_invalido(self, cpf):
        ok, motivo = validar_transacao(tx_valida(cpf=cpf))
        assert ok is False
        assert "cpf" in motivo

    @pytest.mark.parametrize("cpf", [None, 12345678901])
    def test_cpf_de_tipo_invalido(self, cpf):
        assert validar_transacao(tx_valida(cpf=cpf))[0] is False

    # combinações -----------------------------------------------------------
    def test_retorna_o_primeiro_motivo_de_falha(self):
        ok, motivo = validar_transacao(tx_valida(valor_bruto=-1, cpf="1"))
        assert ok is False
        assert "valor_bruto" in motivo

    def test_retorno_eh_tupla_bool_str(self):
        resultado = validar_transacao(tx_valida())
        assert isinstance(resultado, tuple)
        assert isinstance(resultado[0], bool)
        assert isinstance(resultado[1], str)


# --------------------------------------------------------------------------
# calcular_desconto_e_final
# --------------------------------------------------------------------------
class TestCalcularDescontoEFinal:
    @pytest.mark.parametrize(
        "idade, categoria, bruto, desconto, final",
        [
            (30, "vestuario", 100.0, 0.0, 100.0),    # sem desconto
            (25, "eletronicos", 150.0, 0.0, 150.0),  # TX1001
            (18, "eletronicos", 200.0, 0.0, 200.0),  # limite: 18 pode comprar
            (59, "vestuario", 100.0, 0.0, 100.0),    # limite: 59 sem desconto
            (60, "vestuario", 100.0, 15.0, 85.0),    # limite: 60 tem 15%
            (61, "vestuario", 100.0, 15.0, 85.0),
            (30, "livros", 100.0, 10.0, 90.0),       # 10% de livros
            (17, "livros", 80.0, 8.0, 72.0),         # menor compra livros
            (59, "livros", 100.0, 10.0, 90.0),
            (60, "livros", 100.0, 25.0, 75.0),       # acumulado = limite 25%
            (62, "alimentos", 1000.0, 150.0, 850.0),
        ],
    )
    def test_descontos(self, idade, categoria, bruto, desconto, final):
        valor_desconto, valor_final = calcular_desconto_e_final(bruto, idade, categoria)
        assert valor_desconto == pytest.approx(desconto)
        assert valor_final == pytest.approx(final)

    @pytest.mark.parametrize("idade", [0, 10, 17])
    def test_menor_nao_pode_comprar_eletronicos(self, idade):
        with pytest.raises(ValueError, match="eletronicos"):
            calcular_desconto_e_final(100.0, idade, "eletronicos")

    def test_menor_pode_comprar_outras_categorias(self):
        assert calcular_desconto_e_final(100.0, 17, "vestuario") == (0.0, 100.0)

    def test_desconto_acumulado_respeita_limite_maximo(self, monkeypatch):
        # Com as regras atuais o máximo acumulado é exatamente 25%;
        # forçamos livros=20% para provar que o teto de 25% é aplicado.
        monkeypatch.setattr(regra_negocio, "DESCONTO_LIVROS", 0.20)
        desconto, final = calcular_desconto_e_final(100.0, 60, "livros")
        assert desconto == pytest.approx(25.0)
        assert final == pytest.approx(75.0)

    def test_arredondamento_em_duas_casas(self):
        desconto, final = calcular_desconto_e_final(10.01, 60, "vestuario")
        assert desconto == 1.5
        assert final == 8.51

    def test_valor_final_mais_desconto_igual_ao_bruto(self):
        bruto = 350.50
        desconto, final = calcular_desconto_e_final(bruto, 70, "livros")
        assert desconto + final == pytest.approx(bruto)

    def test_retorno_eh_tupla_de_dois_floats(self):
        resultado = calcular_desconto_e_final(100.0, 60, "livros")
        assert isinstance(resultado, tuple)
        assert len(resultado) == 2
        assert all(isinstance(v, float) for v in resultado)


# --------------------------------------------------------------------------
# Casos reais do dados_processamento.json
# --------------------------------------------------------------------------
VALIDACAO_ESPERADA = {
    "TX1001": True,
    "TX1002": True,
    "TX1003": True,
    "TX1004": True,
    "TX1005": False,  # valor negativo
    "TX1006": False,  # CPF curto
    "TX1007": True,
    "TX1008": False,  # valor zero
    "TX1009": True,
    "TX10010": True,
}

CALCULO_ESPERADO = {  # id: (desconto, final)
    "TX1001": (0.0, 150.0),
    "TX1002": (8.0, 72.0),
    "TX1003": (75.0, 425.0),
    "TX1004": (0.0, 200.0),
    "TX1007": (150.0, 850.0),
    "TX1009": (0.0, 350.50),
    "TX10010": (18.0, 102.0),
}


def test_json_possui_exatamente_10_casos():
    dados = carregar_json()
    assert len(dados) == 10
    assert {tx["id_transacao"] for tx in dados} == set(VALIDACAO_ESPERADA)


@pytest.mark.parametrize(
    "transacao", carregar_json(), ids=lambda tx: tx["id_transacao"]
)
def test_validacao_dos_casos_do_json(transacao):
    ok, _ = validar_transacao(transacao)
    assert ok is VALIDACAO_ESPERADA[transacao["id_transacao"]]


@pytest.mark.parametrize("id_transacao", sorted(CALCULO_ESPERADO))
def test_calculo_dos_casos_validos_do_json(id_transacao):
    transacao = next(t for t in carregar_json() if t["id_transacao"] == id_transacao)
    desconto, final = calcular_desconto_e_final(
        transacao["valor_bruto"], transacao["idade"], transacao["categoria"]
    )
    esperado_desconto, esperado_final = CALCULO_ESPERADO[id_transacao]
    assert desconto == pytest.approx(esperado_desconto)
    assert final == pytest.approx(esperado_final)
