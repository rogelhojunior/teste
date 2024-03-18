import logging
from typing import Optional
import pytz

import requests
from django.core.exceptions import ObjectDoesNotExist
from requests import HTTPError

from api_log.constants import EnumStatusCCB
from api_log.models import LogCliente, QitechRetornos
from contract.constants import QI_TECH_ENDPOINTS
from contract.models.contratos import Portabilidade, Contrato, MargemLivre

# from handlers.qitech import QiTech
import handlers
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core import settings
from custom_auth.models import UserProfile


class HandleProposalFinancialPortability:
    def __init__(self, contrato: Contrato):
        self.contract = contrato
        self.portability = None
        self._set_portability()
        self.proposal_key = getattr(self.portability, 'chave_proposta', None)
        self.response: Optional[requests.Response] = None
        self.decoded_response: Optional[dict] = None
        self.logger = logging.getLogger('digitacao')

    def _set_portability(self):
        try:
            self.portability = Portabilidade.objects.get(contrato=self.contract)
        except ObjectDoesNotExist:
            self.portability = None

    def set_response(self):
        raise NotImplementedError

    def handle_http_error(self) -> bool:
        raise NotImplementedError

    def log_success(self, msg: str):
        pass

    def create_qitech_retornos(self, retorno, status: str):
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=self.contract.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=self.contract.cliente,
            retorno=retorno,
            tipo=status,
        )


class RefuseProposalFinancialPortability(HandleProposalFinancialPortability):
    """
    Classe responsável por realizar a recusa de propostas de portabilidade financeira
    """

    def set_response(self):
        qitech = handlers.qitech.QiTech()
        self.response = qitech.refuse_proposal_financial_portability(self.proposal_key)
        self.decoded_response = qitech.decode_body(self.response.json())

    def handle_proposal_financial_portability(self):
        """
        Esse método realiza o fluxo para caso a recusa funcione corretamente
        """
        json_obj_response = self.decoded_response
        self.create_qitech_retornos(json_obj_response, 'DELETE')
        self.portability.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
        self.portability.save(update_fields=['status_ccb'])
        self.log_success('Recusa enviada para QITECH')
        return True

    def handle_error_proposal_financial_portability(self):
        """
        Método para tratar o caso da recusa na QiTech retornar algum erro
        """
        json_obj_response = self.decoded_response
        if (
            json_obj_response.get('code', None) == 'CT000010'
        ):  # Codigo de erro de quando a proposta ja foi cancelada
            self.log_success('Proposta ja havia sido cancelada na QITECH')
            return True

        self.portability.sucesso_recusa_proposta = False
        self.portability.motivo_recusa_proposta = (
            f'Status: {self.response.status_code}\n'
            f" Descrição:{json_obj_response['translation']} {json_obj_response['code']}"
        )
        self.portability.save(
            update_fields=['sucesso_recusa_proposta', 'motivo_recusa_proposta']
        )
        self.logger.warning(
            f'{self.proposal_key} - Contrato({self.contract.pk}):'
            f'Houve um erro ao recusar a proposta.',
            extra=self.decoded_response,
        )
        return False

    def log_success(self, msg: str):
        """
        Método para persistir o sucesso ao recusar proposta e gerar log
        """
        self.portability.sucesso_recusa_proposta = True
        self.portability.save(update_fields=['sucesso_recusa_proposta'])
        self.logger.info(
            f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}):{msg}.\n'
        )

    def execute(self) -> bool:
        """
        Método responsável por executar o fluxo de recusa de proposta
        """
        if self.portability and self.portability.chave_proposta:
            self.set_response()
            try:
                self.response.raise_for_status()
                return self.handle_proposal_financial_portability()
            except HTTPError:
                return self.handle_error_proposal_financial_portability()
        return False


class RefuseProposalFinancialFreeMargin(HandleProposalFinancialPortability):
    """Realiza a recusa da proposta de margem livre na QITECH"""

    STATUS = 'DELETE'

    def __init__(
        self,
        contract: Contrato,
    ):
        super().__init__(contrato=contract)

        self.free_margin = None
        self._set_free_margin()
        self.proposal_key = getattr(self.free_margin, 'chave_proposta', None)

    def _set_free_margin(self):
        try:
            self.free_margin = MargemLivre.objects.get(contrato=self.contract)
        except ObjectDoesNotExist:
            self.free_margin = None

    def _get_body(self):
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        data_hora = self.contract.criado_em.astimezone(sao_paulo_tz)
        data_final = data_hora.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        body = {
            'key': f'{self.proposal_key}',
            'data': {},
            'status': 'canceled_permanently',
            'webhook_type': 'debt',
            'event_datetime': f'{data_final}',
        }
        return {
            'complex_operation': True,
            'operation_batch': body,
        }

    def set_response(self):
        qitech = handlers.qitech.QiTech()
        self.response = qitech.debt_cancel(
            body=self._get_body(), proposal_key=self.proposal_key
        )
        self.decoded_response = qitech.decode_body(self.response.json())

    def log_success(self, msg: str):
        """
        Método para persistir o sucesso ao recusar proposta e gerar log
        """
        self.free_margin.sucesso_recusa_proposta = True
        self.free_margin.save(update_fields=['sucesso_recusa_proposta'])
        self.logger.info(
            f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}):{msg}.\n'
        )

    def handle_proposal_financial_free_margin(self) -> bool:
        self.create_qitech_retornos(self.decoded_response, self.STATUS)
        # self.free_margin.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
        # self.free_margin.save(update_fields=['status_ccb'])
        self.log_success(
            f'(Margem Livre)Sucesso na desaverbação enviada para QITECH.\n Payload {self.decoded_response}'
        )
        return True

    def handle_error_proposal_financial_free_margin(self):
        self.create_qitech_retornos(self.decoded_response, self.STATUS)
        self.free_margin.sucesso_recusa_proposta = False
        self.free_margin.motivo_recusa_proposta = (
            f'Status: {self.response.status_code}\n'
            f" Descrição:{self.decoded_response['title']}"
        )
        self.free_margin.save(
            update_fields=['sucesso_recusa_proposta', 'motivo_recusa_proposta']
        )
        self.logger.warning(
            f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}):'
            f'(Margem Livre)Erro na desaverbação enviada para QITECH.\n Payload {self.decoded_response}'
        )
        return False

    def execute(self) -> bool:
        """
        Método responsável por executar o fluxo de recusa de proposta
        """
        if self.free_margin and self.free_margin.chave_proposta:
            self.set_response()
            try:
                self.response.raise_for_status()
                return self.handle_proposal_financial_free_margin()
            except HTTPError:
                return self.handle_error_proposal_financial_free_margin()
            except Exception as e:
                json_formated = str(e)
                self.create_qitech_retornos(
                    json_formated,
                    'Received Signature',
                )
                self.logger.error(
                    f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}): '
                    f'(Margem Livre)Erro ao realizar a Desaverbação da proposta na QiTech.\n Payload{self.decoded_response}'
                )
                return False
        return False


class AcceptProposalFinancialPortability(HandleProposalFinancialPortability):
    def __init__(
        self,
        contract: Contrato,
        status: str = 'accepted_by_requester',
    ):
        super().__init__(contrato=contract)
        self.status = status

    def handle_accept_proposal_financial_portability(self):
        json_obj_response = self.decoded_response
        self.create_qitech_retornos(json_obj_response, self.status)
        if self.status == 'pending_response':
            self.portability.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
            self.portability.save(update_fields=['status_ccb'])
        self.log_success('Proposta de portabilidade aceita')
        return json_obj_response

    def handle_error_accept_proposal_financial_portability(self):
        json_obj_response = self.decoded_response
        user = UserProfile.objects.get(identifier=settings.QITECH_USER)
        if json_obj_response['code'] == 'SSC000041':
            self.portability.status = ContractStatus.REPROVADO.value
            self.portability.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=self.contract,
                nome=ContractStatus.REPROVADO.value,
                created_by=user,
            )
            RefuseProposalFinancialPortability(contrato=self.contract).execute()
        self.portability.motivo_aceite_proposta = (
            f'Status: {self.response.status_code}\n'
            f" Descrição:{json_obj_response['translation']}\n"
            f"CODIGO ERRO(QITECH) :{json_obj_response['code']}"
        )
        self.portability.sucesso_aceite_proposta = False
        self.portability.save(
            update_fields=['sucesso_aceite_proposta', 'motivo_aceite_proposta']
        )
        self.logger.warning(
            f'{self.proposal_key} - Contrato({self.contract.pk}):'
            f'Houve um erro ao aceitar a proposta.',
            extra=self.decoded_response,
        )
        return False

    def log_success(self, msg: str = ''):
        """
        Método para persistir o sucesso ao aceitar proposta e gerar log
        """
        self.portability.sucesso_aceite_proposta = True
        self.portability.save(update_fields=['sucesso_aceite_proposta'])
        self.logger.info(
            f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}):{msg}.\n'
        )

    def set_response(self):
        qitech = handlers.qitech.QiTech()
        self.response = qitech.accept_proposal_financial_portability(
            self.portability, self.status
        )
        self.decoded_response = qitech.decode_body(self.response.json())

    def execute(self) -> bool:
        """
        Método responsável por executar o fluxo de recusa de proposta
        """
        if self.portability and self.portability.chave_proposta:
            self.set_response()
            try:
                self.response.raise_for_status()
                return bool(self.handle_accept_proposal_financial_portability())
            except HTTPError:
                return self.handle_error_accept_proposal_financial_portability()
        return False


class SubmitFinancialPortabilityProposal(HandleProposalFinancialPortability):
    def __init__(self, contract: Contrato, status: str = 'pending_response'):
        super().__init__(contrato=contract)
        self.status = status

    def set_response(self):
        qitech = handlers.qitech.QiTech()
        self.response = qitech.submit_proposal_financial_portability(
            self.proposal_key, self.status
        )
        self.decoded_response = qitech.decode_body(self.response.json())

    def log_success(self, msg: str):
        """
        Método para persistir o sucesso ao recusar proposta e gerar log
        """
        self.portability.sucesso_submissao_proposta = True
        self.portability.save(update_fields=['sucesso_submissao_proposta'])
        self.logger.info(
            f'{self.contract.cliente.id_unico} - Contrato({self.contract.pk}):{msg}.\n'
        )

    def handle_submit_proposal_financial_portability(self):
        json_obj_response = self.decoded_response
        if self.response.status_code in {200, 201, 202} or self.get_proposal_status():
            self.create_qitech_retornos(json_obj_response, self.status)
            if self.status == 'pending_response':
                self.portability.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
                self.portability.save(update_fields=['status_ccb'])
            message = self.generate_message(success=True)
            self.log_success(msg=message)
            return True
        else:
            self.log_error(json_obj_response)
            return False

    def get_proposal_status(self) -> bool:
        from contract.api.views.get_qi_tech_data import execute_qi_tech_get

        endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + self.proposal_key
        consulta = execute_qi_tech_get(endpoint).data
        return 'proposal_status' in consulta and consulta['proposal_status'] in (
            'pending_response',
            'pending_acceptance'
        )

    def generate_message(self, success=False, exception=None):
        base_message = (
            f'{self.contract.cliente.id_unico} - Contrato(ID: {self.contract.pk}):'
        )
        if success:
            if self.response.status_code in {200, 201, 202}:
                return f'{base_message} Proposta submetida com sucesso.'
            else:
                return f'{base_message} Proposta já havia sido submetida com sucesso.'
        elif exception:
            return f'{base_message} Erro na submissão da proposta (Exception).'
        else:
            return f'{base_message} Erro na submissão da proposta.'

    def log_error(self, json_obj_response):
        self.portability.sucesso_submissao_proposta = False
        self.portability.motivo_submissao_proposta = (
            f'Status: {self.response.status_code}\n'
            f"Descrição:{json_obj_response['translation']}\n"
            f"CODIGO ERRO(QITECH) :{json_obj_response['code']}"
        )
        self.portability.save(
            update_fields=['motivo_submissao_proposta', 'sucesso_submissao_proposta']
        )
        message = self.generate_message()
        self.logger.error(message, extra={'extra': json_obj_response})

    def execute(self) -> bool:
        """
        Método responsável por executar o fluxo de recusa de proposta
        """
        if self.portability and self.portability.chave_proposta:
            self.set_response()
            try:
                return self.handle_submit_proposal_financial_portability()
            except HTTPError as e:
                self.create_qitech_retornos(self.decoded_response, 'Received Signature')
                message = self.generate_message(exception=e)
                self.logger.error(message, extra={'extra': str(e)})
                return False
        return False
