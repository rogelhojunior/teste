import logging
from typing import Literal

from contract.models.contratos import Contrato, Refinanciamento, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade.tasks import approve_refinancing
from custom_auth.models import UserProfile
from handlers.webhook_qitech.exceptions.invalid_process import InvalidProcessException


class CollateralConstitutedPaidBaseProcessor:
    def __init__(
        self,
        contract: Contrato,
        user: UserProfile,
    ):
        self.contract = contract
        self.user = user

    _FINISHED_PORTABILITY_DESCRIPTION = (
        'Portabilidade finalizada, recebido o webhook de averbado e de pago.'
    )
    _WAITING_PAID_CONFIRMATION_PORTABILITY_DESCRIPTION = (
        'Portabilidade averbada pela QITECH, aguardando confirmação do banco de origem.'
    )

    _WAITING_ENDORSEMENT_PORTABILITY_DESCRIPTION = 'Portabilidade PAGA pela QITECH, aguardando retorno da confirmação de averbação.'

    def update_portability(self, status: int):
        self.portability.status = status
        self.portability.save(update_fields=['status'])

    def create_contract_status(self, status: int, description: str):
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=status,
            descricao_mesa=description,
            created_by=self.user,
        )

    def create_waiting_status(self, status: int, description: str):
        self.create_contract_status(status=status, description=description)
        self.update_portability(status=status)

    def finalize_portability(self):
        self.create_contract_status(
            status=ContractStatus.INT_FINALIZADO.value,
            description=self._FINISHED_PORTABILITY_DESCRIPTION,
        )
        self.update_portability(status=ContractStatus.INT_FINALIZADO.value)


class PortabilityCollateralPaidProcessor(CollateralConstitutedPaidBaseProcessor):
    _FINISHED_PORTABILITY_DESCRIPTION = 'Recebido o webhook de averbação.'
    _PAID_PORTABILITY_DESCRIPTION = 'Recebido o webhook de pago.'

    def __init__(
        self, contract: Contrato, portability: Portabilidade, user: UserProfile
    ):
        super().__init__(contract=contract, user=user)
        self.portability = portability

    def create_waiting_status(self, status: int, description: str):
        self.create_contract_status(status=status, description=description)
        if self.portability.status != ContractStatus.INT_FINALIZADO.value:
            self.update_portability(status=status)

    def execute(self, process_type: Literal['paid', 'collateral']):
        try:
            if process_type == 'paid':
                return self.create_waiting_status(
                    status=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                    description=self._PAID_PORTABILITY_DESCRIPTION,
                )
            elif process_type == 'collateral':
                return self.finalize_portability()
            raise InvalidProcessException
        except InvalidProcessException:
            logging.error(
                f'{self.portability.chave_proposta} - Contrato({self.contract.pk}):'
                f'  Este tipo de processo não é válido para a classe - "{process_type}" .',
            )
        except Exception as e:
            logging.error(
                f'{self.portability.chave_proposta} - Contrato({self.contract.pk}):'
                f'  Houve um erro ao processar o webhook de "{process_type}" .',
                extra={'error': str(e)},
            )


class PortabilityRefinancingCollateralPaidProcessor(
    CollateralConstitutedPaidBaseProcessor
):
    def __init__(
        self,
        contract: Contrato,
        portability: Portabilidade,
        refinancing: Refinanciamento,
        user: UserProfile,
    ):
        super().__init__(contract=contract, user=user)
        self.portability = portability
        self.refinancing = refinancing

    def perform_refinancing_acceptance(self):
        return approve_refinancing.apply_async(args=[self.refinancing.pk])

    def process(self, expected_status: int, waiting_status: int, waiting_message: str):
        if StatusContrato.objects.filter(
            contrato=self.contract, nome=expected_status
        ).exists():
            self.finalize_portability()
            self.perform_refinancing_acceptance()
        else:
            self.create_waiting_status(
                status=waiting_status, description=waiting_message
            )

    def execute(self, process_type: Literal['paid', 'collateral']):
        try:
            if process_type == 'paid':
                return self.process(
                    expected_status=ContractStatus.INT_AGUARDANDO_PAGO_QITECH.value,
                    waiting_status=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                    waiting_message=self._WAITING_ENDORSEMENT_PORTABILITY_DESCRIPTION,
                )
            elif process_type == 'collateral':
                return self.process(
                    expected_status=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                    waiting_status=ContractStatus.INT_AGUARDANDO_PAGO_QITECH.value,
                    waiting_message=self._WAITING_PAID_CONFIRMATION_PORTABILITY_DESCRIPTION,
                )
            raise InvalidProcessException
        except InvalidProcessException:
            logging.error(
                f'{self.refinancing.chave_proposta} - Contrato({self.contract.pk}):'
                f'  Este tipo de processo não é válido para a classe - "{process_type}" .',
            )
        except Exception as e:
            logging.error(
                f'{self.refinancing.chave_proposta} - Contrato({self.contract.pk}):'
                f'  Houve um erro ao processar o webhook de "{process_type}" .',
                extra={'error': str(e)},
            )
            raise e
