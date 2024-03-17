from datetime import datetime

from django.test import TestCase

from contract.products.cartao_beneficio.termos import gerar_vencimento_final


class TestGerarVencimentoFinal(TestCase):
    def test_simple_case(self):
        primeiro_vencimento = datetime(2022, 1, 1)
        numero_de_parcelas = 3
        resultado = gerar_vencimento_final(primeiro_vencimento, numero_de_parcelas)
        self.assertEqual(resultado, '01/04/2022')

    def test_zero(self):
        primeiro_vencimento = datetime(2022, 1, 1)
        numero_de_parcelas = 0
        resultado = gerar_vencimento_final(primeiro_vencimento, numero_de_parcelas)
        self.assertEqual(resultado, '01/01/2022')

    def test_next_year(self):
        primeiro_vencimento = datetime(2022, 1, 1)
        numero_de_parcelas = 12
        resultado = gerar_vencimento_final(primeiro_vencimento, numero_de_parcelas)
        self.assertEqual(resultado, '01/01/2023')

    def test_next_5_years(self):
        primeiro_vencimento = datetime(2022, 1, 1)
        numero_de_parcelas = 12 * 5
        resultado = gerar_vencimento_final(primeiro_vencimento, numero_de_parcelas)
        self.assertEqual(resultado, '01/01/2027')
