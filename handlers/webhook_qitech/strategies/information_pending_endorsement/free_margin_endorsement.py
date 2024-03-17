from logging import getLogger
from typing import NoReturn, Optional, Type

from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST

from contract.models.contratos import Contrato, MargemLivre
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile
from handlers.webhook_qitech.dto.information_pending_endorsement.free_margin_endorsement import (
    FreeMarginEndorsementDTO,
)
from handlers.webhook_qitech.enums import QiTechEndorsementErrorEnum
from handlers.webhook_qitech.exceptions.free_margin_endorsement import (
    FreeMarginProposalNotValidException,
)
from handlers.webhook_qitech.strategies.information_pending_endorsement import (
    InformationPendingStrategy,
    OriginalProposalsStatus,
)

logger = getLogger(__name__)


class FreeMarginInformationPendingStrategy(InformationPendingStrategy):
    """
    Implements a strategy for managing 'information pending' scenarios in free margin endorsement processes.

    This class is a part of a strategy pattern, focusing specifically on handling cases where additional
    information is required for processing free margin proposals in credit operation systems. It extends
    the InformationPendingStrategy class, adding specific logic for free margin endorsements.

    Attributes:
        payload_webhook (dict[str, any]): Webhook payload containing endorsement information.
        proposal_dto (Type[FreeMarginEndorsementDTO]): DTO for the free margin endorsement proposal.
        free_margin (MargemLivre): The free margin object related to the proposal.
        contract (Contrato): The contract associated with the free margin.
        user (UserProfile): The user profile linked to the contract.

    Methods:
        __init__: Constructor for initializing the strategy with necessary attributes.
        _get_expected_endorsement_error_types: Identifies expected endorsement error types for free margin.
        _get_endorsement_error_type: Determines the specific endorsement error type from the proposal.
        check_proposal_pending: Checks if the proposal is pending and raises an exception if not.
        execute: Executes the strategy logic for a pending proposal.
    """

    def __init__(
        self,
        payload_webhook: dict[str, any],
        proposal_dto: Type[FreeMarginEndorsementDTO],
    ) -> None:
        """
        Initializes the strategy with the given webhook payload and proposal DTO.

        Args:
            payload_webhook (dict[str, any]): Payload of the webhook, containing endorsement details.
            proposal_dto (Type[FreeMarginEndorsementDTO]): DTO representing the free margin endorsement proposal.
        """
        super().__init__(payload_webhook=payload_webhook, proposal_dto=proposal_dto)
        self.free_margin: MargemLivre = MargemLivre.objects.get(
            chave_proposta=self.proposal_pending.key
        )
        self.contract: Contrato = self.free_margin.contrato
        self.user: UserProfile = self.free_margin.contrato.created_by

    def _get_expected_endorsement_error_types(self) -> tuple:
        """
        Determines the expected types of endorsement errors for free margin endorsements.

        Returns:
            tuple: A tuple of QiTechEndorsementErrorEnum values representing the expected error types.
        """
        return (
            QiTechEndorsementErrorEnum.INVALID_DISBURSEMENT_ACCOUNT,
            QiTechEndorsementErrorEnum.FIRST_NAME_MISMATCH,
            QiTechEndorsementErrorEnum.INVALID_STATE,
            QiTechEndorsementErrorEnum.INVALID_BANK_CODE,
            QiTechEndorsementErrorEnum.WRONG_BENEFIT_NUMBER_ON_PORTABILITY,
            QiTechEndorsementErrorEnum.CONSIGNABLE_MARGIN_EXCEEDED,
        )

    def _get_endorsement_error_type(self) -> QiTechEndorsementErrorEnum:
        """
        Identifies the specific endorsement error type based on the proposal's collateral data.

        Returns:
            QiTechEndorsementErrorEnum: The enum value representing the specific endorsement error type.
        """
        return QiTechEndorsementErrorEnum(
            self.proposal_pending.data.collateral_data.last_response.errors[
                0
            ].enumerator
        )

    def check_proposal_pending(self) -> Optional[NoReturn]:
        """
        Validates if the proposal is still pending and raises an exception if it's not.

        This method checks the 'is_proposal_pending' flag. If the proposal is not pending, it raises
        a FreeMarginProposalNotValidException, indicating the proposal is in an invalid state.

        Returns:
            Optional[NoReturn]: None if the proposal is pending; otherwise, raises an exception.

        Raises:
            FreeMarginProposalNotValidException: If the proposal is not in a pending state.
        """
        if not self.is_proposal_pending:
            raise FreeMarginProposalNotValidException(
                endorsement_error_type=self.endorsement_error_type
            )

    def validate_last_status_contract(self) -> bool:
        last_original_status: StatusContrato = StatusContrato.objects.filter(
            contrato=self.contract,
            original_proposals_status__isnull=False,
        ).last()
        return bool(
            last_original_status
            and last_original_status.nome == ContractStatus.INT_AJUSTE_AVERBACAO.value
            and self.free_margin.status == ContractStatus.INT_AJUSTE_AVERBACAO.value
        )

    def execute(self) -> None:
        from contract.constants import STATUS_REPROVADOS

        """
        Executes the necessary actions when a free margin proposal is pending.

        This method updates the status of the free margin and creates a new status record for the contract.
        It is called when the proposal is pending and the contract is in a specific state that allows for
        further processing.

        Side effects:
            - Updates the status of the free margin object.
            - Creates a new StatusContrato object with the updated status and a description.
        """
        if not StatusContrato.objects.filter(
            contrato=self.contract, nome__in=STATUS_REPROVADOS
        ).exists():
            if self.validate_last_status_contract():
                raise ValidationError(
                    detail={
                        'erro': 'O contrato já está no status de (Int - Ajuste Averbação). '
                        'Por favor, faça o ajuste da pendência no backoffice.'
                    },
                    code=HTTP_400_BAD_REQUEST,
                )

            validate_contract = (
                self.free_margin.status == ContractStatus.INT_AGUARDA_AVERBACAO.value
            )

            if not self.is_proposal_pending and validate_contract:
                raise ValidationError(
                    detail={'erro': 'Contrato não é valido para ajuste de pendência.'},
                    code=HTTP_400_BAD_REQUEST,
                )

            original_proposals_status: dict[str, any] = OriginalProposalsStatus(
                free_margin_status=self.free_margin.status,
            ).to_dict()
            logger.info(
                'Original status of free margin.',
                extra={
                    'free_margin_status': self.free_margin.status,
                    'original_proposals_status': original_proposals_status,
                },
            )

            self.free_margin.status = ContractStatus.INT_AJUSTE_AVERBACAO.value
            self.free_margin.save(update_fields=['status'])

            logger.info(
                'Saving new free margin status',
                extra={'free_margin_status': self.free_margin.status},
            )
            StatusContrato.objects.create(
                contrato=self.contract,
                nome=ContractStatus.INT_AJUSTE_AVERBACAO.value,
                created_by=self.user,
                descricao_mesa=self.pendency_reason,
                original_proposals_status=original_proposals_status,
            )
