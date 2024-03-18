"""This module implements tests for action resimular_port_refin present
on ContratoAdmin."""

# built in
from unittest.mock import MagicMock, patch

# third
from django.test import Client, TestCase

# local
from contract.constants import EnumTipoContrato, EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from core.admin_actions.resimular_port_refin.resimular_port_refin_action_executer import (
    ResimularPortRefinActionExecuter,
)
from core.models.cliente import Cliente
from custom_auth.models import UserProfile

ACTION_NAME = 'resimular_port_refin'


class TestResimularPortRefinAction(TestCase):
    """
    This class implements tests for action resimular_port_refin.
    """

    def setUp(self):
        # create objects
        self.user = UserProfile(name='Test')

        cliente = Cliente.objects.create(
            nome_cliente='Test Resimular Port Refin',
        )

        self.total_contratos = 10
        for i in range(self.total_contratos):
            contrato = Contrato.objects.create(
                cliente=cliente,
                tipo_produto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                cd_contrato_tipo=EnumTipoContrato.REFIN_PORTABILIDADE,
            )
            Portabilidade.objects.create(
                contrato=contrato,
                saldo_devedor=0.0,
                prazo=12,
                parcela_digitada=260.0,
                nova_parcela=200.01,
            )
            Refinanciamento.objects.create(
                contrato=contrato,
                saldo_devedor=0.0,
                prazo=12,
                parcela_digitada=260.0,
                nova_parcela=200.01,
            )

        # assert number of created Contrato's
        expected = self.total_contratos
        actual = Contrato.objects.count()
        self.assertEqual(expected, actual)

        # assert number of created Portabilidade's
        expected = self.total_contratos
        actual = Portabilidade.objects.count()
        self.assertEqual(expected, actual)

        # assert number of created Refinanciamento's
        expected = self.total_contratos
        actual = Refinanciamento.objects.count()
        self.assertEqual(expected, actual)

        # define client
        self.client = Client()

        # define querysets
        self.contratos = Contrato.objects.all()
        self.portabilidades = Portabilidade.objects.all()
        self.refinanciamentos = Refinanciamento.objects.all()

    @patch(
        'core.admin_actions.resimular_port_refin.resimular_port_refin_action_executer.resimular_port_refin_para_contrato.delay'
    )
    def test_call_count(self, mock_main_function):
        # define mock behavior
        mock_main_function.return_value = None

        # create mock request object
        mock_request = MagicMock()
        mock_request.user.identifier = self.user.id

        # call action
        executer = ResimularPortRefinActionExecuter(
            request=mock_request, queryset=self.contratos
        )
        executer.execute()

        # assert call count
        expected = self.total_contratos
        actual = mock_main_function.call_count
        self.assertEqual(expected, actual)
