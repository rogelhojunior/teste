"""This module implements UnicoScoreContractValidator class."""

# local
import logging
from typing import List

from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    Portabilidade,
    SaqueComplementar,
)
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core import settings
from core.common.enums import EnvironmentEnum

# constants
UPDATE_SPECIFIC_STATUS_TYPES = [
    EnumTipoProduto.CARTAO_BENEFICIO,
    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
    EnumTipoProduto.CARTAO_CONSIGNADO,
    EnumTipoProduto.PORTABILIDADE,
    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
    EnumTipoProduto.SAQUE_COMPLEMENTAR,
]
UNICO_DIVERGENCY_STATUS = 2
UNICO_SCORE_SUCCESS_STATUS = 3
RESTRICTIVE_ERROR_SCORE_RANGE = range(-90, -10)
DISAPPROVED_SCORE_RANGE = range(-10, 50)
APPROVED_SCORE_RANGE = range(50, 100)
UNICO_RULE_DESCRIPTION = 'Regra Score UNICO'

logger = logging.getLogger('digitacao')


class UnicoScoreContractValidator:
    """
    UNICO score validator to a contract.

    Attributes:
        contract (Contrato): a reference to the contract
            being updated.
        sub_contract (Portabilidade | CartaoBeneficio |
            SaqueComplementar): a contract have a "tipo_produto"
            attribute, this key inform that there is a record of a
            specific type pointing to this contract, we are naming this
            record as "sub contract" to improve readability. The sub
            contract record must have the status updated too.
    """

    def __init__(self, contract: Contrato) -> None:
        self.contract = contract
        self.envelope = contract.envelope

    @property
    def validation_message(self) -> str:
        """Description message to use on ValidacaoContrato record."""
        return UNICO_RULE_DESCRIPTION

    @property
    def status(self) -> int:
        """Status returned by UNICO saved in the envelope."""
        return self.envelope.status_unico

    @property
    def score(self) -> int:
        """Score returned by UNICO saved in the envelope."""
        if not self.envelope.score_unico:
            return 0
        try:
            # First, attempt to convert directly to an int, which works if the string is a whole number
            return int(self.envelope.score_unico)
        except ValueError:
            # If it fails, try converting to a float first, then to an int
            try:
                return int(float(self.envelope.score_unico))
            except Exception as e:
                logger.error(f'Erro ao tentar converter score da unico: {e}')
                return 0

    @property
    def is_score_approved(self) -> bool:
        """Does the score means approved ?"""
        return self.score in APPROVED_SCORE_RANGE

    @property
    def is_score_disapproved(self) -> bool:
        """Does the score means disapproved ?"""
        return self.score in DISAPPROVED_SCORE_RANGE

    @property
    def is_score_restrictive_error(self) -> bool:
        """Does the score means restrictive error ?"""
        return self.score in RESTRICTIVE_ERROR_SCORE_RANGE

    @property
    def is_unico_status_success(self) -> bool:
        """If status key incoming in the UNICO request is a
        success status."""
        return self.status == UNICO_SCORE_SUCCESS_STATUS

    @property
    def is_unico_status_divergency(self) -> bool:
        """If status key incoming in the UNICO request is a
        divergency status."""
        return self.status == UNICO_DIVERGENCY_STATUS

    def validate(self) -> None:
        """
        Validate contract data, generating and updating necessary
        information.
        """
        # approve
        if self.is_unico_status_success and self.is_score_approved:
            self.approve_contract()

        else:
            message = ''
            contract_status = None
            sub_status = None
            description = ''

            # define Validation to save on ValidacaoContrato record
            if self.is_unico_status_divergency:
                message = 'SCORE REPROVADO Divergencia na Unico'

            else:
                message = f'SCORE REPROVADO Valor: {self.score}'

            # define remaining statuses
            # TODO: Remove card paradinha feature flag
            if self.is_score_disapproved or self.is_unico_status_divergency:
                if self.is_benefit_card_ready_to_be_disapproved():
                    contract_status = EnumContratoStatus.MESA
                    should_go_to_corban_desk = (
                        self.contract.corban.mesa_corban
                        and settings.ENVIRONMENT != EnvironmentEnum.PROD.value
                    )
                    sub_status = (
                        ContractStatus.CHECAGEM_MESA_CORBAN
                        if should_go_to_corban_desk
                        else ContractStatus.CHECAGEM_MESA_FORMALIZACAO
                    )

                elif self.is_portability_ready_to_be_disapproved():
                    contract_status = EnumContratoStatus.CANCELADO
                    sub_status = ContractStatus.REPROVADA_POLITICA_INTERNA.value
                    description = (
                        'Recusada por politíca interna (SF) - Biometria facial'
                    )
            elif self.is_score_restrictive_error:
                if self.is_benefit_card_ready_to_be_disapproved():
                    contract_status = EnumContratoStatus.CANCELADO
                    sub_status = ContractStatus.REPROVADA_FINALIZADA.value

                elif self.is_portability_ready_to_be_disapproved():
                    contract_status = EnumContratoStatus.MESA
                    sub_status = ContractStatus.CHECAGEM_MESA_CORBAN.value
                    description = 'SCORE da UNICO abaixo do aceito'

            self.disapprove_contract(
                message=message,
                status=contract_status,
                sub_status=sub_status,
                description=description,
            )

    def approve_contract(self) -> None:
        """Change current status to score approved."""
        self.update_validation_contract_record(f'SCORE APROVADO Valor: {self.score}')

    def disapprove_contract(
        self, message: str, status: int, sub_status: int, description: str = ''
    ) -> None:
        """
        Change current status to score disapproved.

        Args:
            message (str): the message to use in the Validation record.
            status (int): the status to set on Contrato.
            sub_status (int): the status to set on sub contract record.
            description (str): the description to use in StatusContrato
                record.
        """
        self.update_validation_contract_record(message)
        self.update_status_attributes(status, sub_status)
        self.create_contract_status_record(sub_status, description)

    def update_status_attributes(self, contract_status: int, sub_status: int) -> None:
        """
        Change status attributes on contract and sub-contract records.

        Args:
            contract_status (int): the status to save in the Contrato.
            sub_status (int): the status to save in the sub contract.
        """
        if contract_status is not None:
            self.contract.status = contract_status
            self.contract.save()

        if sub_status is not None and self.does_need_to_update_sub_status():
            record = self.get_sub_contract()
            record.status = sub_status
            record.save()

    def does_need_to_update_sub_status(self) -> bool:
        """
        Check if this contract needs to update not just attribute
        status, but the status of a record referring to this contract
        too.

        Returns:
            bool: does need to update or not.
        """
        return self.contract.tipo_produto in UPDATE_SPECIFIC_STATUS_TYPES

    def create_contract_status_record(self, status: int, description: str = '') -> None:
        """
        Create a StatusContrato record.

        Args:
            status (int): the status to save.
            description (str): the status description.
        """
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=status,
            descricao_mesa=description,
        )

    def is_benefit_card_ready_to_be_disapproved(self) -> bool:
        """
        Check if contract is of type benefit card and wether is ready to
        be disapproved or not.

        Returns:
            bool: is ready to be disapproved or not.
        """
        is_benefit_card = self.contract.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.SAQUE_COMPLEMENTAR,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        )
        ready = not (
            self.is_last_status_in(
                ContractStatus.CHECAGEM_MESA_CORBAN.value,
                ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
            )
        )
        return is_benefit_card and ready

    def is_portability_ready_to_be_disapproved(self) -> bool:
        """
        Check if contract is of type Portability and wether is ready to
        be disapproved or not.

        Returns:
            bool: is ready to be disapproved or not.
        """
        is_portability = self.contract.tipo_produto == EnumTipoProduto.PORTABILIDADE
        ready = not (
            self.is_last_status_in((
                ContractStatus.CHECAGEM_MESA_CORBAN.value,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                ContractStatus.REPROVADO.value,
            ))
        )
        return is_portability and ready

    def update_validation_contract_record(self, message: str) -> None:
        """
        Update the validation record.

        Args:
            message (str): what string to use on 'retorno_hub' attribute.
        """
        contract_validation = self.update_or_create_validation_record()
        contract_validation.retorno_hub = (message,)
        contract_validation.save()

    def update_or_create_validation_record(self) -> ValidacaoContrato:
        """Get the contract validation record, updating fields or
        creating a new one if necessary."""
        contract_validation, _ = ValidacaoContrato.objects.update_or_create(
            contrato=self.contract,
            mensagem_observacao=self.validation_message,
            defaults={
                'mensagem_observacao': self.validation_message,
                'checked': self.is_score_approved,
            },
        )
        return contract_validation

    def get_sub_contract(self) -> Portabilidade | CartaoBeneficio | SaqueComplementar:
        """
        A contract have a "tipo_produto" key, this key inform that there
        is a record of a specific type pointing to this contract, so
        depending on this attribute we can get this record referring to
        the contract. We are naming this record as "sub contract".

        Returns:
            Portabilidade | CartaoBeneficio | SaqueComplementar: the
            record referring to this contract that needs to update the
            status attribute too.
        """
        contract = self.contract
        if contract.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
            return CartaoBeneficio.objects.get(contrato=contract)

        elif contract.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            return Portabilidade.objects.get(contrato=contract)

        elif contract.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            return SaqueComplementar.objects.get(contrato=contract)

        else:
            return None

    def is_last_status_in(self, values: int | List[int]) -> bool:
        """
        Check if the last StatusContrato record of the contract is equal
        one of the listed values. Returns False if no StatusContrato
        exists for the contract.

        Args:
            values (int|List[int]): the values to check.
        """
        # convert to list
        if type(values) is not list:
            values = [values]

        try:
            last_status = self.contract.last_status
        except StatusContrato.DoesNotExist:
            return False
        else:
            return last_status.nome in values
