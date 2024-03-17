"""This module implements tests for view CriarContratoSaqueComplementar."""

# built in
from unittest.mock import patch

# third
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

# local
from contract.models.contratos import SaqueComplementar
from contract.products.cartao_beneficio.api.views import CriarContratoSaqueComplementar
from core.models.cliente import Cliente, ClienteCartaoBeneficio
from custom_auth.models import UserProfile


class CriarContratoSaqueComplementarViewTestCase(TestCase):
    """
    This class implements tests for CriarContratoSaqueComplementar view.
    """

    def setUp(self):
        # create auth user for this operation
        self.user = UserProfile.objects.create(
            identifier='1',
            name='test',
        )

        self.django_client = Client()
        self.django_client.defaults['HTTP_AUTHORIZATION'] = self.get_bearer_token()

        # create a client to the test
        self.client = Cliente.objects.create(
            nu_cpf='111.111.111-11',
        )

        # create card client
        self.cart_client = ClienteCartaoBeneficio.objects.create()

        # define default payload
        self.payload = {
            'numero_cpf': self.client.nu_cpf,
            'taxa_produto': 1.1,
            'taxa_anual_produto': 1.1,
            'cet_mensal': 1.1,
            'cet_anual': 1.1,
            'valor_iof_total': 1.1,
            'vr_iof_adicional': 1.1,
            'valor_iof_diario_em_dinheiro': 1.1,
            'vencimento': '1111-11-11',
            'limite_disponivel_saque': 1.0,
            'valor_lancado_fatura': 1.0,
            'valor_saque': 1.0,
            'saque_parcelado': True,
            'possui_saque': True,
            'valor_parcela': 1,
            'qtd_parcela_saque_parcelado': 1,
            'somatorio_parcelas': 1,
            'limite_pre_aprovado': 1,
            'id_cliente_cartao': self.cart_client.id,
            'inicio_digitacao': 1,
        }

        # define url
        self.url = reverse('criar_contrato_saque_complementar')

    def get_bearer_token(self):
        """
        Obtains a bearer token for the request.
        """
        token = AccessToken.for_user(self.user)
        return f'Bearer {token}'

    @patch.object(CriarContratoSaqueComplementar, 'post')
    def test_called_once(self, mock_post):
        # mock post function
        mocked_return = Response({'test': 'test'}, status=200)
        mock_post.return_value = mocked_return

        # call view
        response = self.django_client.post(self.url, self.payload)

        # perform assertions
        self.assertEqual(mock_post.call_count, 1)
        self.assertIsInstance(response, Response)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data.get('test'), 'test')

    def test_floor_valor_saque(self):
        """
        When executing the view the value present in key "valor_saque"
        sent to the view must be rounded to floor.
        """
        # define values to be tested
        test_values = [0, 1.1, 2.23, 5.5134132, 10041123.124342654252]
        expected_values = [0, 1.1, 2.23, 5.51, 10041123.12]
        total_records = 0

        for i, test_value in enumerate(test_values):
            # edit payload
            self.payload['valor_saque'] = test_value

            # call view
            self.assertEqual(SaqueComplementar.objects.count(), total_records)
            response = self.django_client.post(self.url, self.payload)
            self.assertIsInstance(response, Response)
            self.assertEqual(response.status_code, 200)

            # retrieve created SaqueComplementar
            self.assertEqual(SaqueComplementar.objects.count(), total_records + 1)
            total_records += 1
            created_record = SaqueComplementar.objects.last()
            actual = float(created_record.valor_saque)
            self.assertEqual(actual, expected_values[i])
