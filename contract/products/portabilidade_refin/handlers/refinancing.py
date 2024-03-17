import logging
from typing import Optional

import requests
from requests import HTTPError
from rest_framework.exceptions import ValidationError

from api_log.constants import EnumStatusCCB
from contract.models.contratos import Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from handlers.qitech import QiTech


class HandleRefinancing:
    def __init__(self, refinancing: Refinanciamento):
        self.refinancing = refinancing
        self.contract = self.refinancing.contrato
        self.response: Optional[requests.Response] = None
        self.decoded_response: Optional[dict] = None

        self.logger = logging.getLogger('webhookqitech')

    def update_refinancing(self):
        raise NotImplementedError

    def create_contract_status(self):
        raise NotImplementedError

    def set_response(self):
        raise NotImplementedError

    def handle_http_error(self) -> bool:
        raise NotImplementedError

    def log_success(self):
        pass

    def execute(self) -> bool:
        assert (
            self.refinancing.chave_proposta
        ), 'É obrigatório que o refinanciamento possua chave da proposta'
        self.set_response()
        try:
            self.response.raise_for_status()
            self.log_success()
            self.update_refinancing()
            self.create_contract_status()
            return True
        except HTTPError as e:
            self.handle_http_error()
            raise ValidationError(
                {'erro': 'Não foi possível confirmar o refinanciamento na QI tech'},
            ) from e


class AcceptRefinancing(HandleRefinancing):
    """
    Class for refinancing accept
    """

    def set_response(self):
        qitech = QiTech()

        self.response = qitech.accept_refinancing_fixed_disbursed_change(
            self.refinancing
        )
        self.decoded_response = qitech.decode_body(self.response.json())
        # Caso dê erro por causa do Teto do INSS, tenta aceitar o Refin fixando a taxa.
        if self.decoded_response.get('code') == 'COP000296':
            self.response = qitech.accept_refinancing(self.refinancing)
            self.decoded_response = qitech.decode_body(self.response.json())

    def update_refinancing(self):
        self.refinancing.status = ContractStatus.AGUARDANDO_AVERBACAO_REFIN.value
        self.refinancing.numero_contrato = self.decoded_response['contract_number']
        self.refinancing.document_url_qitech_ccb = self.decoded_response['document_url']
        self.refinancing.credit_operation_status = self.decoded_response[
            'credit_operation_status'
        ]
        self.refinancing.document_key_QiTech_CCB = self.decoded_response['document_key']
        self.refinancing.taxa_contrato_recalculada = (
            self.decoded_response['disbursement_options'][0]['prefixed_interest_rate'][
                'monthly_rate'
            ]
            * 100
        )

        self.refinancing.troco_recalculado = self.decoded_response[
            'final_disbursement_amount'
        ]
        self.refinancing.valor_total_recalculado = self.decoded_response[
            'disbursement_options'
        ][0]['issue_amount']
        self.refinancing.save()

    def create_contract_status(self):
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=ContractStatus.AGUARDANDO_AVERBACAO_REFIN.value,
            descricao_mesa='Portabilidade finalizada, aguardando averbação do Refin',
        )

    def log_success(self):
        self.refinancing.sucesso_aceite_proposta = True
        self.refinancing.save()
        self.logger.info(
            f'{self.refinancing.chave_proposta} - Contrato({self.contract.pk}):'
            f'  Refinanciamento aprovado com sucesso',
        )

    def handle_http_error(self) -> bool:
        self.refinancing.sucesso_aceite_proposta = False
        self.refinancing.motivo_aceite_proposta = 'erro no aceite da proposta'
        self.refinancing.save()
        self.logger.warning(
            f'{self.refinancing.chave_proposta} - Contrato({self.contract.pk}):'
            f' Houve um erro ao aprovar o Refinanciamento.',
            extra=self.decoded_response,
        )
        return False


class CancelRefinancing(HandleRefinancing):
    """
    Class for refinancing cancelment
    """

    def __init__(
        self,
        refinancing: Refinanciamento,
        reason: str,
        status: str = ContractStatus.REPROVADO.value,
        ccb_status: str = EnumStatusCCB.REJECTED.value,
    ):
        super().__init__(refinancing)
        self.reason = reason
        self.status = status
        self.ccb_status = ccb_status

    def update_refinancing(self):
        self.refinancing.status = self.status
        self.refinancing.status_ccb = self.ccb_status
        self.refinancing.save()

    def update_status_contrato(self):
        StatusContrato.objects.create(
            contrato=self.contract,
            descricao_mesa=self.reason,
            nome=ContractStatus.REPROVADO.value,
        )

    def update_portablity(self):
        port = Portabilidade.objects.get(contrato=self.contract)
        port.status = ContractStatus.REPROVADO.value
        port.save(update_fields=['status'])

    def execute(self) -> bool:
        self.update_refinancing()
        self.update_status_contrato()
        self.update_portablity()
        return True


class PutRefinancingOnHold(HandleRefinancing):
    """
    Class for putting refinancing on hold
    """

    def __init__(
        self,
        refinancing: Refinanciamento,
        portability: Portabilidade,
        reason: str,
    ):
        super().__init__(refinancing)
        self.portability = portability
        self.reason = reason

    def update_refinancing(self):
        self.portability.status = (
            ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
        )
        self.portability.save(update_fields=['status'])

        StatusContrato.objects.create(
            contrato=self.contract,
            nome=ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value,
            descricao_mesa=self.reason,
        )

    def execute(self) -> bool:
        self.update_refinancing()
        return True
