"""This module implements the class ResimularPortRefinActionExecuter."""

# built-in
import logging

# local
from contract.constants import EnumTipoProduto
from contract.products.portabilidade.tasks import resimular_port_refin_para_contrato
from core.admin_actions.contrato_action_executer import ContratoActionExecuter

# globals
logger = logging.getLogger(__file__)
ENABLED_PRODUCTS = (EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,)


class ResimularPortRefinActionExecuter(ContratoActionExecuter):
    """
    This class implements functions to execute action resimular_por_refin
    used in the contract admin.
    """

    def execute(self):
        """Execute action."""
        for contrato in self.queryset:
            if contrato.tipo_produto in ENABLED_PRODUCTS:
                resimular_port_refin_para_contrato.delay(
                    contrato.id, self.request.user.id
                )
