import unittest

from django.test import TestCase

from contract.tests.base_test import BaseTestContext
from handlers.validar_regras_beneficio_contrato import (
    ValidadorRegrasBeneficioContratoMargemLivre,
)


class BaseTestBenefitContractRules(BaseTestContext, TestCase):
    def setUp(self):
        """
        Initial teste configuration
        Creates all the instances needed for testing
        - Age groups
        - Client
        - Sales representative
        - Bank correspondent
        - Contract
        - In100 Data
        """
        self.create_age_groups()
        self.client = self.create_client()
        self.sales_representative = self.create_sales_representative()
        self.bank_correspondent = self.create_bank_correspondent(
            self.sales_representative
        )
        self.contract = self.create_contract(self.client, self.bank_correspondent)
        self.in100_data = self.create_in100_data(self.client)


class TestValidatorBenefitContractFreeMarginRules(BaseTestBenefitContractRules):
    def setUp(self):
        super().setUp()
        self.free_margin = self.create_free_margin(self.contract)

    def test_validate_death_rule_approved(self):
        """
        Validates when the death rule is applied and is invalid.
        """
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_morte()
        self.assertTrue(resposta['regra_aprovada'])

    def test_validate_death_rule_denied(self):
        """
        Validates when the death rule is applied and is valid.
        """
        self.contract.cd_contrato_tipo = 2
        self.in100_data.dt_expedicao_beneficio = None
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_morte()
        self.assertFalse(resposta['regra_aprovada'])
        self.assertEqual(resposta['motivo'], 'Não possui data de concessão')

    def test_validate_age_group_approved(self):
        """
        Validates when the group age is valid and rule is approved.
        """
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_faixa_idade()
        self.assertTrue(resposta['regra_aprovada'])

    def test_validate_age_group_denied(self):
        """
        Validates when the group age is invalid.
        !TODO Create failure test!
        """
        self.set_client_age(self.client, 77)
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_faixa_idade()
        self.assertFalse(resposta['regra_aprovada'])

    # Checking approved cases for age group

    def base_test_age_group_approved(self, age: int, contract_value: float):
        """
        Validates when the group age is invalid.

        """
        self.set_client_age(self.client, age)
        self.set_contract_value(self.free_margin, contract_value)
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_faixa_idade()
        self.assertTrue(resposta['regra_aprovada'])

    def test_validate_age_group_21_73_approved(self):
        self.base_test_age_group_approved(50, 60000)

    def test_validate_age_group_74_75_approved(self):
        self.base_test_age_group_approved(74, 40000)

    def test_validate_age_group_75_76_approved(self):
        self.base_test_age_group_approved(75, 25000)

    def test_validate_age_group_76_77_approved(self):
        self.base_test_age_group_approved(76, 15000)

    def test_validate_age_group_77_78_approved(self):
        self.base_test_age_group_approved(77, 10000)

    def test_validate_age_group_78_79_approved(self):
        self.base_test_age_group_approved(78, 8000)

    def test_validate_age_group_79_80_approved(self):
        self.base_test_age_group_approved(79, 4000)

    # Checking denied cases for age group

    def base_test_age_group_denied(self, age: int, contract_value: float):
        """
        Validates when the group age is invalid.

        """
        self.set_client_age(self.client, age)
        self.set_contract_value(self.free_margin, contract_value)
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        resposta = validador.validar_regra_faixa_idade()
        self.assertFalse(resposta['regra_aprovada'])

    def test_validate_age_group_21_73_denied(self):
        self.base_test_age_group_denied(50, 90000)

    def test_validate_age_group_74_75_denied(self):
        self.base_test_age_group_denied(74, 60000)

    def test_validate_age_group_75_76_denied(self):
        self.base_test_age_group_denied(75, 40000)

    def test_validate_age_group_76_77_denied(self):
        self.base_test_age_group_denied(76, 25000)

    def test_validate_age_group_77_78_denied(self):
        self.base_test_age_group_denied(77, 20000)

    def test_validate_age_group_78_79_denied(self):
        self.base_test_age_group_denied(78, 15000)

    def test_validate_age_group_79_80_denied(self):
        self.base_test_age_group_denied(79, 8000)

    def test_get_soma_contratos(self):
        """
        Tests method get_soma_contratos(), in free margin needs to equal to vr_contrato.
        """
        validador = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contract, self.in100_data
        )
        soma = validador.get_valor_contrato()
        self.assertEqual(str(soma), self.free_margin.vr_contrato)


class TestValidatorBenefitContractPortabilityRules(BaseTestBenefitContractRules):
    def setUp(self):
        super().setUp()
        self.portability = self.create_portability(self.contract)


# Execute os testes
if __name__ == '__main__':
    unittest.main()
