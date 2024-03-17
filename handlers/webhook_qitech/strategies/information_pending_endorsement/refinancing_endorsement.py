from logging import getLogger
from typing import NoReturn, Optional, Type

from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST

from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile
from handlers.webhook_qitech.dto.information_pending_endorsement.refinancing_endorsement import (
    RefinancingEndorsementDTO,
)
from handlers.webhook_qitech.enums import QiTechEndorsementErrorEnum
from handlers.webhook_qitech.exceptions.refinancing_endorsement import (
    RefinancingProposalNotValidException,
)
from handlers.webhook_qitech.strategies.information_pending_endorsement import (
    InformationPendingStrategy,
    OriginalProposalsStatus,
)

logger = getLogger(__name__)


class RefinancingInformationPendingStrategy(InformationPendingStrategy):
    def __init__(
        self,
        payload_webhook: dict[str, any],
        proposal_dto: Type[RefinancingEndorsementDTO],
    ) -> None:
        super().__init__(payload_webhook=payload_webhook, proposal_dto=proposal_dto)
        self.portability: Portabilidade = Portabilidade.objects.get(
            chave_proposta=self.proposal_pending.key
        )
        self.refinancing: Refinanciamento = Refinanciamento.objects.get(
            chave_proposta=self.proposal_pending.key
        )
        self.contract: Contrato = self.portability.contrato
        self.user: UserProfile = self.portability.contrato.created_by

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
            raise RefinancingProposalNotValidException(
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
            and self.refinancing.status == ContractStatus.INT_AJUSTE_AVERBACAO.value
        )

    def execute(self) -> None:
        from contract.constants import STATUS_REPROVADOS

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

            last_original_status: StatusContrato = StatusContrato.objects.filter(
                contrato=self.contract,
                original_proposals_status__isnull=False,
            ).last()
            if (
                last_original_status
                and last_original_status.nome
                == ContractStatus.INT_AJUSTE_AVERBACAO.value
            ):
                return

            validate_contract = (
                # Alteração somente em Port
                self.portability.status == ContractStatus.INT_AGUARDA_AVERBACAO.value
                and self.refinancing.status
                == ContractStatus.AGUARDANDO_FINALIZAR_PORT.value
            ) or (  # Alteração em Port e Refin
                self.portability.status == ContractStatus.INT_FINALIZADO.value
                and self.refinancing.status
                == ContractStatus.AGUARDANDO_AVERBACAO_REFIN.value
            )

            if not self.is_proposal_pending and validate_contract:
                raise ValidationError(
                    detail={'erro': 'Contrato não é valido para ajuste de pendência.'},
                    code=HTTP_400_BAD_REQUEST,
                )

            original_proposals_status: dict[str, any] = OriginalProposalsStatus(
                portability_status=self.portability.status,
                refinancing_status=self.refinancing.status,
            ).to_dict()
            logger.info(
                'Original status of portability and refinancing.',
                extra={
                    'portability_status': self.portability.status,
                    'refinancing_status': self.refinancing.status,
                    'original_proposals_status': original_proposals_status,
                },
            )

            self.refinancing.status = ContractStatus.INT_AJUSTE_AVERBACAO.value
            self.refinancing.save(update_fields=['status'])

            logger.info(
                'saving new portability status',
                extra={'portability_status': self.portability.status},
            )
            logger.info(
                'saving new refinancing status',
                extra={'refinancing_status': self.refinancing.status},
            )

            StatusContrato.objects.create(
                contrato=self.contract,
                nome=ContractStatus.INT_AJUSTE_AVERBACAO.value,
                created_by=self.user,
                descricao_mesa=self.pendency_reason,
                original_proposals_status=original_proposals_status,
            )
