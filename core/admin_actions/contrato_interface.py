"""This module implements ContratoInterface class."""

# built in
import logging

# local
from contract.constants import STATUS_REPROVADOS
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.products.cartao_beneficio.constants import ContractStatus

# globals
logger = logging.getLogger(__file__)


class ContratoInterface:
    def __init__(self, contrato: Contrato) -> None:
        self.contrato = contrato
        self.port = None
        self.refin = None
        self.error_message = ''

        try:
            self.port = Portabilidade.objects.get(contrato=contrato)
        except Portabilidade.DoesNotExist:
            logger.warning(self.build_missing_port_warning_message())
        except Portabilidade.MultipleObjectsReturned:
            logger.warning(self.build_multiple_port_warning_message())

        try:
            self.refin = Refinanciamento.objects.get(contrato=contrato)
        except Refinanciamento.DoesNotExist:
            logger.warning(self.build_missing_refin_warning_message())
        except Refinanciamento.MultipleObjectsReturned:
            logger.warning(self.build_multiple_refin_warning_message())

    @property
    def is_valid(self) -> bool:
        if not bool(self.port):
            self.error_message = 'Missing Portabilidade'
            return False

        elif not bool(self.refin):
            self.error_message = 'Missing refinanciamento'
            return False

        return True

    @property
    def is_port_endorsed(self) -> bool:
        return self.port.status == ContractStatus.INT_FINALIZADO.value

    @property
    def is_refin_endorsed(self) -> bool:
        return self.refin.status == ContractStatus.INT_FINALIZADO.value

    @property
    def is_port_reproved(self) -> bool:
        return self.port.status in STATUS_REPROVADOS

    @property
    def is_refin_reproved(self) -> bool:
        return self.refin.status in STATUS_REPROVADOS

    def build_missing_port_warning_message(self) -> str:
        return self.build_waning_message('portabilidade')

    def build_missing_refin_warning_message(self) -> str:
        return self.build_waning_message('refinanciamento')

    def build_missing_product_warning_message(self, product: str) -> str:
        msg = 'Contrato %d não possui %s' % (self.contrato.id, product)
        return msg

    def build_multiple_port_warning_message(self) -> str:
        return self.build_multiple_products_warning_message('portabilidade')

    def build_multiple_refin_warning_message(self) -> str:
        return self.build_multiple_products_warning_message('refinanciamento')

    def build_multiple_products_warning_message(self, product: str) -> str:
        msg = 'Contrato %d possui múltiplos contratos de %s' % (
            self.contrato.id,
            product,
        )
        return msg

    def get_operation_key(self) -> str:
        operation_key = self.refin.chave_operacao
        return operation_key

    def endorse_port(self) -> None:
        self.port.status = ContractStatus.INT_FINALIZADO.value
        self.port.save(update_fields=['status'])
        logger.info('Status de Port atualizado com sucesso')

    def rewind_port_endorsement(self) -> None:
        self.port.status = ContractStatus.INT_AGUARDA_AVERBACAO.value
        self.port.save(update_fields=['status'])
        logger.info('Status de Port atualizado com sucesso')
