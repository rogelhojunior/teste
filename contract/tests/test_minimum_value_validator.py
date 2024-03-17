"""
Implements tests for MinimumValueValidator class.
"""
# built-in
from unittest.mock import patch

# third
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import AccessToken

# local
from contract.constants import EnumTipoProduto
from contract.services.validators.minimum_value import MinimumValueValidator
from core.models.cliente import Cliente
from core.models.parametro_produto import ParametrosProduto
from custom_auth.models import UserProfile


class TestMinimumValueValidator(TestCase):

    def setUp(self):
        self.min_value = 5000
        self.valid_value = 5000
        self.invalid_value = 4999.99


    def test_port_refin_valid(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade_refinanciamento': [{'valor_operacao': self.valid_value}],
        }

        # validator should not raise Validation error
        MinimumValueValidator(payload).validate()


    def test_port_refin_invalid(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade_refinanciamento': [{'valor_operacao': self.invalid_value}]
        }

        with self.assertRaises(ValidationError):
            MinimumValueValidator(payload).validate()


    def test_port_refin_valid_multiple(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade_refinanciamento': [
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
            ],
        }

        # validator should not raise Validation error
        MinimumValueValidator(payload).validate()


    def test_port_refin_invalid_multiple(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade_refinanciamento': [
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.valid_value},
                {'valor_operacao': self.invalid_value}, # the bad guy
            ],
        }

        with self.assertRaises(ValidationError):
            MinimumValueValidator(payload).validate()


    def test_port_valid(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade': [{'saldo_devedor': self.valid_value}],
        }

        # validator should not raise Validation error
        MinimumValueValidator(payload).validate()


    def test_port_invalid(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade': [{'saldo_devedor': self.invalid_value}]
        }

        with self.assertRaises(ValidationError):
            MinimumValueValidator(payload).validate()


    def test_port_valid_multiple(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade': [
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
            ],
        }

        # validator should not raise Validation error
        MinimumValueValidator(payload).validate()


    def test_port_invalid_multiple(self):
        tipo_produto = EnumTipoProduto.PORTABILIDADE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'portabilidade': [
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.valid_value},
                {'saldo_devedor': self.invalid_value}, # the bad guy
            ],
        }

        with self.assertRaises(ValidationError):
            MinimumValueValidator(payload).validate()


    def test_margem_livre_valid(self):
        tipo_produto = EnumTipoProduto.MARGEM_LIVRE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'vr_contrato': self.valid_value,
        }

        # validator should not raise Validation error
        MinimumValueValidator(payload).validate()


    def test_margem_livre_invalid(self):
        tipo_produto = EnumTipoProduto.MARGEM_LIVRE

        # create parameters for the product on the database
        ParametrosProduto.objects.create(
            tipoProduto=tipo_produto,
            valor_minimo_emprestimo=self.valid_value
        )

        # create payload
        payload = {
            'tipo_produto': tipo_produto,
            'vr_contrato': self.invalid_value,
        }

        with self.assertRaises(ValidationError):
            MinimumValueValidator(payload).validate()

RANDOM_CPF = '08253154097'
class TestCriarContratoViewMinimumValueValidation(TestCase):
    def setUp(self):
        # create auth user for this operation
        self.user = UserProfile.objects.create(
            identifier='1',
            name='test',
        )
        self.django_client = Client()
        self.django_client.defaults['HTTP_AUTHORIZATION'] = self.get_bearer_token()

        self.url :str = reverse('criar-contrato')
        self.cliente :Cliente = Cliente.objects.create(
            nu_cpf=RANDOM_CPF
        )

    def get_bearer_token(self):
        """
        Obtains a bearer token for the request.
        """
        token = AccessToken.for_user(self.user)
        return f'Bearer {token}'

    @patch('contract.services.validators.minimum_value.MinimumValueValidator')
    def test_criar_contrato_port_refin(self, MockMinimumValueValidator):
        # prepare mock
        mock = MockMinimumValueValidator

        # send request
        tipo_produto = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
        payload = {
            'portabilidade_refinanciamento': [
                {
                    'valor_operacao': 13980.19,
                }
            ],
            'id_cliente': self.cliente.id,
            'tipo_produto': tipo_produto,
            'numero_cpf': self.cliente.nu_cpf,
        }
        response = self.django_client.post(self.url, data=payload)

        # assert
        mock.validate.assert_called_once()
