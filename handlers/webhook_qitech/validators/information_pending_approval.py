from logging import getLogger
from typing import Type, TypeVar

from django.core.exceptions import ObjectDoesNotExist
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from handlers.webhook_qitech.dto.information_pending_endorsement.free_margin_endorsement import (
    FreeMarginEndorsementDTO,
)
from handlers.webhook_qitech.dto.information_pending_endorsement.portability_endorsement import (
    PortabilityEndorsementDTO,
)
from handlers.webhook_qitech.dto.information_pending_endorsement.refinancing_endorsement import (
    RefinancingEndorsementDTO,
)
from handlers.webhook_qitech.exceptions import PendingRatioNotSupportedException
from handlers.webhook_qitech.strategies.information_pending_endorsement.free_margin_endorsement import (
    FreeMarginInformationPendingStrategy,
)
from handlers.webhook_qitech.strategies.information_pending_endorsement.portability_endorsement import (
    PortabilityInformationPendingStrategy,
)
from handlers.webhook_qitech.strategies.information_pending_endorsement.refinancing_endorsement import (
    RefinancingInformationPendingStrategy,
)
from handlers.webhook_qitech.utils import PydanticValidationErrorFormatter

logger = getLogger(__name__)

WebHookResponseModelType = TypeVar('WebHookResponseModelType', bound=BaseModel)
StrategiesType = Type[
    PortabilityInformationPendingStrategy
    | RefinancingInformationPendingStrategy
    | FreeMarginInformationPendingStrategy
]


class ProposalInformationPendingApprovalValidator:
    __strategies: dict[WebHookResponseModelType:StrategiesType] = {
        PortabilityEndorsementDTO: PortabilityInformationPendingStrategy,
        RefinancingEndorsementDTO: RefinancingInformationPendingStrategy,
        FreeMarginEndorsementDTO: FreeMarginInformationPendingStrategy,
    }
    proposal_dto: Type[WebHookResponseModelType]

    def __init__(self, payload_webhook: dict[str, any]) -> None:
        self.payload_webhook: dict[str, any] = payload_webhook

    def get_proposal_dto(self) -> Type[WebHookResponseModelType]:
        try:
            self.payload_webhook.get('data', {}).get('collateral_data', {}).get(
                'reservation_method'
            )
            reservation_method: str = (
                self.payload_webhook.get('data', {})
                .get('collateral_data', {})
                .get('reservation_method')
            )
            webhook_type: str = self.payload_webhook.get('webhook_type')

            if webhook_type == 'credit_operation.collateral':
                if reservation_method == 'new_credit':
                    return FreeMarginEndorsementDTO
                elif reservation_method == 'refinancing':
                    return RefinancingEndorsementDTO
            elif webhook_type == 'credit_transfer.proposal.collateral':
                return PortabilityEndorsementDTO

            raise DRFValidationError(
                detail={'erro': 'payload de pendência no formato errado'},
                code=HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            raise DRFValidationError(
                detail={'erro': 'payload de pendência no formato errado'},
                code=HTTP_400_BAD_REQUEST,
            ) from e

    def set_proposal_dto(self) -> None:
        try:
            self.proposal_dto: Type[WebHookResponseModelType] = self.get_proposal_dto()
            logger.info(f'proposal type {self.proposal_dto.__name__}')
        except PydanticValidationError:
            raise

    def __get_strategy(self) -> StrategiesType:
        try:
            return self.__strategies[self.proposal_dto]
        except KeyError as e:
            raise ValueError(
                f'Strategy not found {self.proposal_dto.__name__} for provided payload_webhook.'
            ) from e

    def execute(self) -> None:
        try:
            logger.info(
                'start execution of ProposalInformationPendingApprovalValidator'
            )
            self.set_proposal_dto()

            strategy: StrategiesType = self.__get_strategy()
            strategy(
                payload_webhook=self.payload_webhook,
                proposal_dto=self.proposal_dto,
            ).execute()
            logger.info('end execution of ProposalInformationPendingApprovalValidator')
        except PydanticValidationError as e:
            errors_fields: dict[str, any] = (
                PydanticValidationErrorFormatter.format_error(exception=e)
            )
            proposal_type: str = self.proposal_dto.__name__.split('Endorsement')[0]
            message: dict[str, any] = {
                'message': f'Payload of {proposal_type} in the wrong format',
                'errors': errors_fields,
            }
            logger.warning(
                msg='Incompatible payload with pending proposal validation.',
                extra={
                    'payload_webhook': self.payload_webhook,
                    'errors_fields': errors_fields,
                },
                exc_info=True,
            )
            raise DRFValidationError(detail=message, code=HTTP_400_BAD_REQUEST) from e
        except PendingRatioNotSupportedException as e:
            logger.warning(
                msg=f'Pending reason {e.endorsement_error_type} not valid for internal treatment',
                exc_info=True,
            )
        except ObjectDoesNotExist as e:
            logger.exception(
                'proposal not found', extra={'payload_webhook': self.payload_webhook}
            )
            raise DRFValidationError(
                detail={'erro': 'Proposta não encontrada'}, code=HTTP_404_NOT_FOUND
            ) from e
        except Exception:
            logger.exception(
                'Something wrong when running ProposalInformationPendingApprovalValidator',
                extra={'payload_webhook': self.payload_webhook},
            )
            raise
