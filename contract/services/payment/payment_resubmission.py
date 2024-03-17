import logging
from datetime import datetime
from typing import Union

import requests
from requests import HTTPError
from rest_framework.exceptions import ValidationError

from contract.constants import EnumTipoProduto
from contract.models.contratos import CartaoBeneficio, MargemLivre, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.services.persistance.logs import create_log_records
from handlers.qitech import QiTech
from utils.bank import get_brazilian_bank, get_client_bank_data
from utils.date import get_next_weekday


class PaymentResubmission:
    """
    This class has the main goal to perform payment resubmission
     when one product of types Free Margin or Portability, Refinancing and benefit card had the payment denied by some reason.
    """

    def __init__(self, product: Union[MargemLivre, Refinanciamento, CartaoBeneficio]):
        self.product = product
        self.contract = self.product.contrato
        self.client = self.contract.cliente
        self.qi_tech = QiTech()

    def update_product_disbursement_date(self, disbursement_date: datetime.date):
        self.product.dt_desembolso = disbursement_date
        self.product.save(update_fields=['dt_desembolso'])

    def send_payment_resubmission(self, disbursement_date) -> requests.Response:
        client_bank_data = get_client_bank_data(client=self.client)
        return self.qi_tech.payment_resubmission(
            proposal_key=self.product.chave_proposta,
            disbursement_date=str(disbursement_date),
            bank_account=client_bank_data,
            bank=get_brazilian_bank(bank_code=client_bank_data.conta_banco),
            cpf=self.client.nu_cpf_,
            customer_name=self.client.nome_cliente,
            product_type=self.contract.tipo_produto,
        )

    def process_payment_resubmission_response(self, response: requests.Response):
        logger = logging.getLogger('webhookqitech')
        decoded_response = self.qi_tech.decode_body(response_json=response.json())

        create_log_records(
            client=self.client,
            data=decoded_response,
            log_type='Reapresentação de pagamento',
        )

        try:
            response.raise_for_status()
            logging.info(
                f'{self.client.id_unico} - Contrato({self.contract.pk})'
                f' ({self.contract.get_tipo_produto_display()}) Reapresentado com sucesso.',
                extra=decoded_response,
            )
            if (
                self.contract.tipo_produto
                == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
            ):
                self.product.status = ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value
                StatusContrato.objects.create(
                    contrato=self.contract,
                    nome=ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value,
                    descricao_mesa='Reapresentado, AGUARDANDO DESEMBOLSO (REFINANCIAMENTO)',
                )
            elif self.contract.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                self.product.status = ContractStatus.AGUARDANDO_DESEMBOLSO.value
                StatusContrato.objects.create(
                    contrato=self.contract,
                    nome=ContractStatus.AGUARDANDO_DESEMBOLSO.value,
                    descricao_mesa='Reapresentado, AGUARDANDO DESEMBOLSO (MARGEM LIVRE)',
                )
            self.product.sucesso_reapresentacao_pagamento = True
            self.product.save()
            message = f'{self.client.id_unico} - Contrato({self.contract.pk}): Reapresentado com SUCESSO.'
            logger.info(message, extra={'extra': decoded_response})

        except HTTPError as e:
            logging.error(
                f'{self.client.id_unico} - Contrato({self.contract.pk})'
                f' ({self.contract.get_tipo_produto_display()}) Erro na reapresentação do Pagamento.\n',
                extra=decoded_response,
            )
            self.product.sucesso_reapresentacao_pagamento = False
            self.product.motivo_reapresentacao_pagamento = decoded_response[
                'description'
            ]
            self.product.save()
            message = f'{self.client.id_unico} - Contrato({self.contract.pk}): Erro na REAPRESENTAÇÃO'
            logger.error(message, extra={'extra': decoded_response})
            raise ValidationError('Erro ao reapresentar o pagamento') from e

    def execute(self):
        disbursement_date = get_next_weekday()
        self.update_product_disbursement_date(disbursement_date)
        response = self.send_payment_resubmission(disbursement_date)
        self.process_payment_resubmission_response(response)

    def execute_today(self):
        disbursement_date = datetime.now().strftime('%Y-%m-%d')
        self.update_product_disbursement_date(disbursement_date)
        response = self.send_payment_resubmission(disbursement_date)
        self.process_payment_resubmission_response(response)
