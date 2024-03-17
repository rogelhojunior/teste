"""This module implements class QiTechProposalInserter"""

# built in imports
import logging
from datetime import datetime
from typing import Optional

import requests

# django imports
from django.conf import settings
from django.utils import timezone
from requests import HTTPError, RequestException, Response, Timeout

from api_log.constants import EnumStatusCCB

# local imports
from api_log.models import LogWebhook
from contract.constants import EnumContratoStatus, EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato, Portabilidade
from contract.models.envelope_contratos import EnvelopeContratos

# third party imports
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.views import (
    atualizar_contrato_portabilidade,
    get_status_reprovacao,
    status_envio_link_portabilidade,
    validar_regra_especie,
)
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from core.models import Cliente
from handlers.insere_proposta_inss_financeira import autenticacao_hub
from message_bus.consumers.face_match_handler import send_to_web_socket_server
from .payload_builder import PayloadBuilder

# constants


# global variables
logger = logging.getLogger('digitacao')


class QiTechProposalInsertException(Exception):
    def __init__(self):
        self.message = (
            'An error occurred when trying to insert the proposal within IQTech'
        )
        super().__init__(self.message)


class CCBAttachmentException(Exception):
    def __init__(self):
        self.message = 'Error in the CCD attachment url'
        super().__init__(self.message)


class QiTechProposalInserter:
    CONST_HUB_FINANCEIRA_QITECH_URL: str = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )
    TYPES_OF_BENEFIT_THAT_NEEDS_VALIDATION: tuple[int] = (
        4,
        5,
        6,
        32,
        33,
        34,
        51,
        83,
        87,
        92,
    )
    REQUEST_TIMEOUT: int = 120  # Request Timeout in seconds

    response: Response = Response()
    response_json: Optional[dict[str, any]] = None
    payload: Optional[dict[str, any]] = None
    ccb_url: str = ''
    is_proposal_valid: bool = False
    invalid_proposal_reason: str = ''

    def __init__(self, contract_token: str):
        self.contract: Contrato = self.__get_contract_by_token(token=contract_token)
        self.envelope: EnvelopeContratos = self.__get_contract_envelope()
        # self.portability: Portabilidade = self.contract.contrato_portabilidade.get(contrato=self.contract)
        self.portability: Portabilidade = Portabilidade.objects.get(
            contrato=self.contract
        )
        self.client: Cliente = self.contract.cliente
        self.in100: DadosIn100 = DadosIn100.objects.filter(
            numero_beneficio=self.contract.numero_beneficio, cliente=self.client
        ).first()
        self.request_token: str = self.__get_request_token()
        self.payload: dict[str, any] = PayloadBuilder(self.contract).build()

    def __get_contract_envelope(self):
        try:
            return EnvelopeContratos.objects.get(
                token_envelope=self.contract.token_envelope
            )
        except EnvelopeContratos.DoesNotExist:
            logger.exception(
                msg='EnvelopeContratos not found',
                extra={'contract_token': str(self.contract.token_envelope)},
            )
            raise

    @staticmethod
    def __get_request_token() -> str:
        return autenticacao_hub()

    @staticmethod
    def __get_contract_by_token(token: str) -> Contrato:
        try:
            return Contrato.objects.get(token_contrato=token)
        except Contrato.DoesNotExist:
            logger.exception(
                msg='Contract with provided token not found', extra={'token': token}
            )
            raise

    def __make_request(
        self, endpoint: str, headers: dict[str, str], body: dict[str, any]
    ) -> Response:
        """
        Make an HTTP POST request to the specified endpoint.

        Parameters
        ----------
        endpoint : str
            The API endpoint URL.
        headers : dict[str, str]
            The headers to be included in the request.
        body : dict[str, any]
            The body of the request.

        Returns
        -------
        requests.Response
            The response object from the HTTP request.
        """
        try:
            self.response = requests.post(
                url=endpoint, headers=headers, json=body, timeout=self.REQUEST_TIMEOUT
            )
            self.response.raise_for_status()
        except (HTTPError, ConnectionError, Timeout, RequestException) as err:
            logger.exception(
                msg=f'Error occurred in call {endpoint}: {err}',
                extra={
                    'endpoint': endpoint,
                    'headers': headers,
                    'status_code': (
                        self.response.status_code
                        if isinstance(err, HTTPError)
                        else None
                    ),
                    'error_type': type(err).__name__,
                },
            )
            raise
        except Exception as err:
            logger.exception(
                msg='Something worng in IQ Request',
                extra={
                    'endpoint': endpoint,
                    'headers': headers,
                    'error_type': type(err).__name__,
                },
            )
            raise

        logger.info(
            msg=f'Successful call to {endpoint}.',
            extra={
                'endpoint': endpoint,
                'headers': headers,
                'status_code': self.response.status_code,
            },
        )
        return self.response

    def __set_reponse_qitech(self):
        """
        Defines the response with the return of direct integration with qitech.
        ----------
        """
        from handlers.qitech import QiTech

        try:
            qitech = QiTech()
            self.response = qitech.insert_proposal_port(self.payload.get('JsonBody'))
            self.response.raise_for_status()
            self.response_json = qitech.decode_body(self.response.json())
        except (HTTPError, ConnectionError, Timeout, RequestException) as err:
            logger.exception(
                msg=f"Error occurred in call {self.payload.get('NmEndpoint')}: {err}",
                extra={
                    'status_code': (
                        self.response.status_code
                        if isinstance(err, HTTPError)
                        else None
                    ),
                    'error_type': type(err).__name__,
                },
            )
            raise
        except Exception as err:
            logger.exception(
                msg='Something worng in IQ Request',
                extra={
                    'endpoint': self.payload.get('NmEndpoint'),
                    'error_type': type(err).__name__,
                },
            )
            raise
        logger.info(
            msg=f"Successful call to {self.payload.get('NmEndpoint')}.",
            extra={
                'endpoint': self.payload.get('NmEndpoint'),
                'status_code': self.response.status_code,
            },
        )

    def send_proposal(self) -> None:
        self.__set_reponse_qitech()

    def insert_proposal(self):
        self.portability.is_proposal_being_inserted = True
        self.portability.save(update_fields=['is_proposal_being_inserted'])

        try:
            self.send_proposal()
        except HTTPError:
            self.treat_unsuccessful_response_data()
        else:
            try:
                self.treat_successful_response_data()
            except CCBAttachmentException:
                self.set_portability_to_error_state()
                self.set_ccb_was_generated(False)
                self.create_webhook_log_error_record()
                logger.exception('Something wrong with response proposal.')
                raise

            if self.are_all_proposals_inserted():
                self.send_ok_though_web_socket()

        finally:
            self.portability.is_proposal_being_inserted = False
            self.portability.save(update_fields=['is_proposal_being_inserted'])

    def create_webhook_log_error_record(self) -> None:
        record_date = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'WEBHOOK QITECH ERRO - INSERÇÃO DA PROPOSTA {record_date}',
            log_webhook=str(self.response_json),
        )

    def set_portability_to_error_state(self) -> None:
        self.portability.is_proposal_being_inserted = False
        self.portability.sucesso_insercao_proposta = False
        self.portability.insercao_sem_sucesso = self.response_json or self.response.text
        self.portability.save(
            update_fields=[
                'is_proposal_being_inserted',
                'sucesso_insercao_proposta',
                'insercao_sem_sucesso',
            ]
        )

    def treat_unsuccessful_response_data(self) -> None:
        self.set_portability_to_error_state()
        self.set_ccb_was_generated(False)
        self.create_webhook_log_error_record()
        logger.error(
            msg='Something wrong when insert proposal in IQTech',
            extra={
                'request_url': self.response.request.url,
                'request_headers': self.response.request.headers,
                'response_status_code': self.response.status_code,
                'response_text': self.response.text,
            },
        )
        raise QiTechProposalInsertException

    def __treat_in100_status(self) -> None:
        self.in100 = status_envio_link_portabilidade(contrato=self.contract, user=None)

    def extract_first_and_last_due_date(self) -> tuple[str, str]:
        installments = (
            self.response_json.get('portability_credit_operation', {})
            .get('disbursement_options')[0]
            .get('installments')
        )

        first_due_date = installments[0].get('due_date')
        last_due_date = installments[-1].get('due_date')

        return first_due_date, last_due_date

    def treat_successful_response_data(self) -> None:
        self.ccb_url: str = self.response_json['portability_credit_operation'][
            'document_url'
        ]

        first_due_date, last_due_date = self.extract_first_and_last_due_date()
        self.portability.dt_primeiro_pagamento = datetime.fromisoformat(
            first_due_date
        ).date()
        self.portability.dt_ultimo_pagamento = datetime.fromisoformat(
            last_due_date
        ).date()
        self.portability.save(
            update_fields=[
                'dt_primeiro_pagamento',
                'dt_ultimo_pagamento',
            ]
        )

        if not self.ccb_url.startswith('http'):
            logger.error(
                msg='An error occurred when trying to obtain the CCB from the financial institution',
                extra={'ccb_url': self.ccb_url},
            )
            raise CCBAttachmentException

        if not self.validate_proposal():
            self.refuse_proposal()
            return

        self.__treat_in100_status()
        if not self.is_in100_return_data():
            logger.warning(
                msg='IN100 has not yet returned. Proposal was neither approved nor rejected.',
                extra={
                    'client_pk': self.client.pk,
                    'contract_pk': self.contract.pk,
                    'in100_return': getattr(self.in100, 'retornou_IN100', False),
                },
            )
        else:
            logger.info(
                msg='IN100 returned proposal, will be accepted.',
                extra={
                    'client_pk': self.client.pk,
                    'contract_pk': self.contract.pk,
                    'in100_return': getattr(self.in100, 'retornou_IN100', False),
                },
            )
            self.accept_proposal()

        self.create_contract_ccb_attachment()
        self.set_ccb_was_generated(True)

        self.portability.ccb_gerada = True
        self.portability.save(update_fields=['ccb_gerada'])

        self.update_portability_with_proposal_response_data()
        logger.info(
            msg='Proposal insert with successfully in QITech',
            extra={
                'client_pk': self.client.pk,
                'client_id_unico': str(self.client.id_unico),
                'contract_pk': self.contract.pk,
            },
        )

    def accept_proposal(self) -> None:
        if not self.contract.is_there_any_client_formalization_status():
            atualizar_contrato_portabilidade(
                contract=self.contract,
                contract_status=EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                portability_status=ContractStatus.FORMALIZACAO_CLIENTE.value,
                table_description=self.portability.insercao_sem_sucesso or '-',
            )

    def refuse_proposal(self) -> None:
        atualizar_contrato_portabilidade(
            contract=self.contract,
            contract_status=EnumContratoStatus.CANCELADO,
            portability_status=ContractStatus.REPROVADO.value,
            table_description=self.invalid_proposal_reason,
        )
        RefuseProposalFinancialPortability(contrato=self.contract).execute()

    def validate_proposal(self) -> bool:
        if self.is_contract_status_reproved():
            self.invalid_proposal_reason = 'Contrato esta com status reprovado'
            return False

        if self.is_specie_not_registered():
            self.invalid_proposal_reason = (
                f'{self.in100.cd_beneficio_tipo} - Especie não cadastrada'
            )
            return False

        if self.is_benefit_blocked():
            self.invalid_proposal_reason = 'Beneficio bloqueado ou cessado'
            return False

        if self.does_specie_needs_validation():
            if self.evaluate_specie_rules():
                return True
            self.invalid_proposal_reason = 'Fora da Politica'
            return False

        return True

    def update_portability_with_proposal_response_data(self) -> None:
        self.portability.related_party_key = self.response_json['borrower'][
            'related_party_key'
        ]
        self.portability.chave_proposta = str(self.response_json['proposal_key'])
        self.portability.chave_operacao = str(
            self.response_json['portability_credit_operation']['credit_operation_key']
        )
        self.portability.status_ccb = EnumStatusCCB.PENDING_SUBIMISSION.value

        self.portability.is_proposal_being_inserted = False
        self.portability.sucesso_insercao_proposta = True
        self.portability.save(
            update_fields=[
                'related_party_key',
                'chave_proposta',
                'chave_operacao',
                'status_ccb',
                'is_proposal_being_inserted',
                'sucesso_insercao_proposta',
            ]
        )

    def create_contract_ccb_attachment(self) -> AnexoContrato:
        return AnexoContrato.objects.create(
            contrato=self.contract,
            anexo_url=self.ccb_url,
            nome_anexo=(
                f'CCB Gerada pela Financeira - Contrato {self.portability.numero_contrato}'
            ),
            anexo_extensao='pdf',
            tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
        )

    def set_ccb_was_generated(self, generated: bool) -> None:
        self.contract.is_ccb_generated = generated
        self.contract.save(update_fields=['is_ccb_generated'])

    def is_in100_return_data(self) -> bool:
        in100_id = getattr(self.in100, 'id', None)
        self.in100 = DadosIn100.objects.filter(id=in100_id).first()
        return getattr(self.in100, 'retornou_IN100', False)

    def is_specie_not_registered(self) -> bool:
        does_specie_exists = self.in100.does_in100_specie_exists()
        return not does_specie_exists

    def is_contract_status_reproved(self) -> bool:
        status = self.contract.get_last_status()
        return status.nome in get_status_reprovacao()

    def is_benefit_blocked(self) -> bool:
        return self.in100.situacao_beneficio in ('INELEGÍVEL', 'BLOQUEADA', 'BLOQUEADO')

    def does_specie_needs_validation(self) -> bool:
        return (
            self.in100.cd_beneficio_tipo in self.TYPES_OF_BENEFIT_THAT_NEEDS_VALIDATION
        )

    def evaluate_specie_rules(self) -> str:
        in100 = self.in100
        validation_data = validar_regra_especie(
            in100.cd_beneficio_tipo, in100.cliente, in100.numero_beneficio
        )
        return validation_data['regra_aprovada']

    def send_ok_though_web_socket(self) -> None:
        data = {'message': 'all done', 'type': 'CONTRACTS_PROCESSED'}
        send_to_web_socket_server(
            socket_id=str(self.envelope.token_envelope), data=data
        )

    def are_all_proposals_inserted(self) -> bool:
        return not self.envelope.is_any_proposal_being_inserted()
