from logging import getLogger
from typing import NoReturn, Optional, Type

from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST

from contract.models.contratos import Contrato, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile
from handlers.webhook_qitech.dto.information_pending_endorsement.portability_endorsement import (
    PortabilityEndorsementDTO,
)
from handlers.webhook_qitech.enums import QiTechEndorsementErrorEnum
from handlers.webhook_qitech.exceptions.portability_endorsement import (
    PortabilityProposalNotValidException,
)
from handlers.webhook_qitech.strategies.information_pending_endorsement import (
    InformationPendingStrategy,
    OriginalProposalsStatus,
)

logger = getLogger(__name__)


class PortabilityInformationPendingStrategy(InformationPendingStrategy):
    def __init__(
        self,
        payload_webhook: dict[str, any],
        proposal_dto: Type[PortabilityEndorsementDTO],
    ) -> None:
        super().__init__(payload_webhook=payload_webhook, proposal_dto=proposal_dto)
        self.portability: Portabilidade = Portabilidade.objects.get(
            chave_proposta=self.proposal_pending.proposal_key
        )
        self.contract: Contrato = self.portability.contrato
        self.user: UserProfile = self.contract.created_by

    def _get_expected_endorsement_error_types(self) -> tuple:
        return (
            QiTechEndorsementErrorEnum.INVALID_DISBURSEMENT_ACCOUNT,
            QiTechEndorsementErrorEnum.FIRST_NAME_MISMATCH,
            QiTechEndorsementErrorEnum.INVALID_STATE,
            QiTechEndorsementErrorEnum.INVALID_BANK_CODE,
            QiTechEndorsementErrorEnum.WRONG_BENEFIT_NUMBER_ON_PORTABILITY,
            QiTechEndorsementErrorEnum.CONSIGNABLE_MARGIN_EXCEEDED,
        )

    def _get_endorsement_error_type(self) -> QiTechEndorsementErrorEnum:
        return QiTechEndorsementErrorEnum(
            self.proposal_pending.data.collateral_data.last_response.errors[
                0
            ].enumerator
        )

    def check_proposal_pending(self) -> Optional[NoReturn]:
        if not self.is_proposal_pending:
            raise PortabilityProposalNotValidException(
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
            and self.portability.status == ContractStatus.INT_AJUSTE_AVERBACAO.value
        )

    def execute(self) -> None:
        from contract.constants import STATUS_REPROVADOS

        if not StatusContrato.objects.filter(
            contrato=self.contract, nome__in=STATUS_REPROVADOS
        ).exists():
            if not self.validate_last_status_contract():
                validate_contract = (
                    self.portability.status
                    == ContractStatus.INT_AGUARDA_AVERBACAO.value
                )

                if not self.is_proposal_pending and validate_contract:
                    raise ValidationError(
                        detail={
                            'erro': 'Contrato não é valido para ajuste de pendência.'
                        },
                        code=HTTP_400_BAD_REQUEST,
                    )

                original_proposals_status: dict[str, any] = OriginalProposalsStatus(
                    portability_status=self.portability.status,
                ).to_dict()
                logger.info(
                    'Original status of portability.',
                    extra={
                        'portability_status': self.portability.status,
                        'original_proposals_status': original_proposals_status,
                    },
                )

                self.portability.status = ContractStatus.INT_AJUSTE_AVERBACAO.value
                self.portability.save(update_fields=['status'])

                logger.info(
                    'saving new portability status',
                    extra={'portability_status': self.portability.status},
                )
                StatusContrato.objects.create(
                    contrato=self.contract,
                    nome=ContractStatus.INT_AJUSTE_AVERBACAO.value,
                    created_by=self.user,
                    descricao_mesa=self.pendency_reason,
                    original_proposals_status=original_proposals_status,
                )
