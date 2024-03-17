"""
This module implements the class MinimumValueValidator.
"""

from typing import List
from contract.constants import EnumTipoProduto
from core.models.parametro_produto import ParametrosProduto
from rest_framework.exceptions import ValidationError

ERROR_MESSAGE = 'O valor mínimo para esse tipo de contrato é %0.2f'


class MinimumValueValidator:
    """
    This class implements methods to validate the value of a contract
    before creation.
    """

    def __init__(self, payload: int):
        self.payload = payload
        self.tipo_produto = int(self.payload.get('tipo_produto'))

    def validate(self) -> None:
        """
        Validate contract minimum value.
        """
        product_parameters = ParametrosProduto.objects.get(
            tipoProduto=self.tipo_produto
        )
        min_value = product_parameters.valor_minimo_emprestimo

        try:
            received_values = self._get_received_values()
        except NotImplementedError:
            return None

        for value in received_values:
            if value < min_value:
                message = ERROR_MESSAGE % min_value
                raise ValidationError(message)

    def _get_received_values(self) -> List[float]:
        """
        Extract the contract value received from the payload.
        """
        if self.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            return [
                item['valor_operacao']
                for item in self.payload['portabilidade_refinanciamento']
            ]

        elif self.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            return [item['saldo_devedor'] for item in self.payload['portabilidade']]

        elif self.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            return [self.payload['vr_contrato']]

        else:
            raise NotImplementedError
