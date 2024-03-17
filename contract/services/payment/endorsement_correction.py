import logging
from datetime import datetime
from typing import Union

import requests
from requests import HTTPError
from rest_framework.exceptions import ValidationError

from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Refinanciamento, Portabilidade, MargemLivre
from contract.services.persistance.logs import create_log_records
from handlers.qitech import QiTech
from handlers.webhook_qitech.enums import PendencyReasonEnum
from utils.bank import get_brazilian_bank, get_client_bank_data
from utils.date import get_next_weekday


class EndorsementCorrection:
    """
    This class has the main goal to perform payment resubmission
     when one product of types Free Margin or Portability, Refinancing and benefit card had the payment denied by some reason.
    """

    def __init__(
        self,
        product: Union[Refinanciamento, Portabilidade, MargemLivre],
        type_correction: str,
        request_type: str,
    ):
        self.product = product
        self.contract = self.product.contrato
        self.client = self.contract.cliente
        self.type_correction = type_correction
        self.request_type = request_type
        self.qi_tech = QiTech()

    def update_product_disbursement_date(self, disbursement_date: datetime.date):
        if self.request_type == 'refinancing':
            self.product.dt_desembolso = disbursement_date
            self.product.save(update_fields=['dt_desembolso'])

    def send_endorsement_correction(self, disbursement_date) -> requests.Response:
        client_bank_data = get_client_bank_data(client=self.client)
        if self.request_type == 'portability':
            key = self.product.chave_operacao
        else:
            key = self.product.chave_proposta
        return self.qi_tech.endorsement_correction(
            contract=self.contract,
            proposal_key=key,
            disbursement_date=str(disbursement_date),
            bank_account=client_bank_data,
            bank=get_brazilian_bank(bank_code=client_bank_data.conta_banco),
            cpf=self.client.nu_cpf_,
            customer_name=self.client.nome_cliente,
            type_correction=self.type_correction,
            request_type=self.request_type,
        )

    def process_endorsement_correction_response(self, response: requests.Response):
        decoded_response = self.qi_tech.decode_body(response_json=response.json())
        logger = logging.getLogger('webhookqitech')
        create_log_records(
            client=self.client,
            data=decoded_response,
            log_type='Reapresentação da Averbação',
        )

        try:
            response.raise_for_status()
            logging.info(
                f'{self.client.id_unico} - Contrato({self.contract.pk})'
                f' ({self.contract.get_tipo_produto_display()}) Averbação reapresentada com sucesso.',
                extra=decoded_response,
            )
            if self.type_correction in (
                PendencyReasonEnum.BANK_NUMBER,
                PendencyReasonEnum.BANK_DETAILS,
            ):
                AnexoContrato.objects.create(
                    contrato=self.contract,
                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                    nome_anexo=f'REAPRESENTAÇÃO AVERBAÇÃO ASSINADA-{self.client.nu_cpf}',
                    anexo_extensao='pdf',
                    anexo_url=decoded_response['signed_url'],
                )
            message = f'{self.client.id_unico} - Contrato({self.contract.pk}): Averbação reapresentada com SUCESSO.'
            logger.info(message, extra={'extra': decoded_response})
        except HTTPError as e:
            logging.error(
                f'{self.client.id_unico} - Contrato({self.contract.pk})'
                f' ({self.contract.get_tipo_produto_display()}) Erro na reapresentação da averbação.\n',
                extra=decoded_response,
            )
            message = f'{self.client.id_unico} - Contrato({self.contract.pk}): Erro na reapresentação da averbação'
            logger.error(message, extra={'extra': decoded_response})
            raise ValidationError('Erro ao reapresentar a averbação') from e

    def execute(self):
        disbursement_date = get_next_weekday()
        self.update_product_disbursement_date(disbursement_date)
        response = self.send_endorsement_correction(disbursement_date)
        self.process_endorsement_correction_response(response)

    def execute_today(self):
        disbursement_date = datetime.now().strftime('%Y-%m-%d')
        self.update_product_disbursement_date(disbursement_date)
        response = self.send_endorsement_correction(disbursement_date)
        self.process_endorsement_correction_response(response)
