from abc import ABC, abstractmethod
from typing import NoReturn, Optional, Type, TypeVar

from pydantic import BaseModel

from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from handlers.webhook_qitech.dto import WEBHOOK_ENDORSEMENT_ERRORS_TYPE
from handlers.webhook_qitech.enums import PendencyReasonEnum, QiTechEndorsementErrorEnum
from handlers.webhook_qitech.exceptions import PendingRatioNotSupportedException

WebHookResponseModelType = TypeVar('WebHookResponseModelType', bound=BaseModel)


class InformationPendingStrategy(ABC):
    """
    Base abstract class for handling 'information pending' scenarios in webhook processing.

    Provides a framework for implementing strategies for different types of pending
    endorsements in webhook responses. Designed to be extended by specific implementations
    for various endorsement types.

    Attributes:
        proposal_pending (WebHookResponseModelType): Validated proposal data from webhook.
        endorsement_error_type (WEBHOOK_ENDORSEMENT_ERRORS_TYPE): Type of endorsement error.
        expected_endorsement_error_types (tuple): Tuple of expected endorsement error types.
        pendency_reason (str): Reason for pendency, derived from the endorsement error.

    Methods:
        __init__(self, payload_webhook, proposal_dto): Initializes the strategy.
        _get_expected_endorsement_error_types(self): Returns expected endorsement error types.
        get_pendency_reason(self): Determines pendency reason based on endorsement error.
        __get_valid_data(proposal_dto, payload_webhook): Validates and returns proposal data.
        _get_endorsement_error_type(self): Abstract method for endorsement error type.
        is_proposal_pending(self): Checks if the proposal is pending.
        check_proposal_pending(self): Abstract method to handle pending proposal status.
        execute(self): Abstract method for executing strategy logic.
    """

    def __init__(
        self,
        payload_webhook: dict[str, any],
        proposal_dto: Type[WebHookResponseModelType],
    ) -> None:
        """
        Initializes with webhook payload and proposal DTO.

        Args:
            payload_webhook (dict[str, any]): Payload from webhook.
            proposal_dto (Type[WebHookResponseModelType]): DTO class for validating payload.
        """
        self.proposal_pending = self.__get_valid_data(
            proposal_dto=proposal_dto, payload_webhook=payload_webhook
        )
        self.endorsement_error_type: WEBHOOK_ENDORSEMENT_ERRORS_TYPE = (
            self._get_endorsement_error_type()
        )
        self.expected_endorsement_error_types: tuple = (
            self._get_expected_endorsement_error_types()
        )
        self.pendency_reason = self.get_pendency_reason()

    def _get_expected_endorsement_error_types(self) -> tuple:
        """
        Returns expected types of endorsement errors.

        Returns:
            tuple: Expected QiTechEndorsementErrorEnum error types.
        """
        return (
            QiTechEndorsementErrorEnum.INVALID_DISBURSEMENT_ACCOUNT,
            QiTechEndorsementErrorEnum.FIRST_NAME_MISMATCH,
            QiTechEndorsementErrorEnum.INVALID_STATE,
            QiTechEndorsementErrorEnum.INVALID_BANK_CODE,
            QiTechEndorsementErrorEnum.WRONG_BENEFIT_NUMBER_ON_PORTABILITY,
            QiTechEndorsementErrorEnum.CONSIGNABLE_MARGIN_EXCEEDED,
        )

    def get_pendency_reason(self) -> str:
        """
        Determines the reason for pendency based on the specific type of endorsement error.

        This method maps the endorsement error type to a corresponding pendency reason using
        predefined mappings. It's designed to handle various error types and translate them into
        understandable pendency reasons.

        Returns:
            str: The reason for pendency, derived from the endorsement error type.

        Raises:
            PendingRatioNotSupportedException: If the endorsement error type does not have a
            corresponding mapped pendency reason.
        """
        try:
            return {
                QiTechEndorsementErrorEnum.INVALID_DISBURSEMENT_ACCOUNT.value: PendencyReasonEnum.BANK_DETAILS.value,
                QiTechEndorsementErrorEnum.FIRST_NAME_MISMATCH.value: PendencyReasonEnum.CLIENT_NAME.value,
                QiTechEndorsementErrorEnum.INVALID_STATE.value: PendencyReasonEnum.STATE.value,
                QiTechEndorsementErrorEnum.INVALID_BANK_CODE.value: PendencyReasonEnum.BANK_NUMBER.value,
                QiTechEndorsementErrorEnum.WRONG_BENEFIT_NUMBER_ON_PORTABILITY.value: PendencyReasonEnum.BENEFIT_NUMBER.value,
                QiTechEndorsementErrorEnum.CONSIGNABLE_MARGIN_EXCEEDED.value: PendencyReasonEnum.MARGIN_EXCEEDED.value,
            }[self.endorsement_error_type]
        except KeyError as e:
            raise PendingRatioNotSupportedException(
                endorsement_error_type=self.endorsement_error_type
            ) from e

    @staticmethod
    def __get_valid_data(
        proposal_dto: Type[WebHookResponseModelType], payload_webhook: dict[str, any]
    ) -> WebHookResponseModelType:
        """
        Validates and returns proposal data using DTO.

        Args:
            proposal_dto (Type[WebHookResponseModelType]): DTO class for payload.
            payload_webhook (dict[str, any]): Webhook payload.

        Returns:
            WebHookResponseModelType: Validated proposal data.
        """
        return proposal_dto.model_validate(payload_webhook)

    @abstractmethod
    def _get_endorsement_error_type(self) -> WEBHOOK_ENDORSEMENT_ERRORS_TYPE:
        """
        Abstract method to get endorsement error type.

        Implement in subclasses to define how error type is determined.

        Returns:
            WEBHOOK_ENDORSEMENT_ERRORS_TYPE: Endorsement error type.
        """
        raise NotImplementedError(
            'Implement a valid __get_endorsement_error_type function'
        )

    @property
    def is_proposal_pending(self) -> bool:
        """
        Checks if proposal is pending based on error type.

        Returns:
            bool: True if pending, False otherwise.
        """
        return self.endorsement_error_type in self.expected_endorsement_error_types

    @abstractmethod
    def check_proposal_pending(self) -> Optional[NoReturn]:
        """
        Abstract method to check and handle pending proposal.

        Implement in subclasses to define handling logic.
        """
        pass

    @abstractmethod
    def execute(self) -> None:
        """
        Abstract method to execute strategy logic.

        Implement in subclasses to define action steps.
        """
        pass


class OriginalProposalsStatus(BaseModel):
    portability_status: Optional[int] = None
    refinancing_status: Optional[int] = None
    free_margin_status: Optional[int] = None

    def to_dict(self):
        return self.model_dump(exclude_none=True)
