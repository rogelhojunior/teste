import logging
from datetime import datetime
from typing import Literal, Union

from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from handlers.qitech import QiTech

logger = logging.getLogger('digitacao')


class HandleQitechResponse:
    def __init__(self, contract: Contrato):
        self.contract = contract
        self.portability = None
        self.refinancing = None
        self.attachment = None
        self.response = None
        self.decoded_response = None
        self.client = contract.cliente

    def insert_proposal_port_refin_response(self):
        qi_tech = QiTech()
        self.response = qi_tech.insert_proposal_port_refin(self.contract)
        self.decoded_response = qi_tech.decode_body(response_json=self.response.json())
        self.set_portability()
        self.set_refinancing()
        self.insert_response()
        return self.response.status_code

    def set_portability(self) -> None:
        self.portability = Portabilidade.objects.filter(contrato=self.contract).first()

    def set_refinancing(self) -> None:
        self.refinancing = Refinanciamento.objects.filter(
            contrato=self.contract
        ).first()

    def create_port_attachment(self) -> None:
        url = self.decoded_response['portability_credit_operation']['document_url']
        AnexoContrato.objects.create(
            contrato=self.contract,
            anexo_url=url,
            nome_anexo=f'CCB Gerada pela Financeira - Contrato Portabilidade {self.portability.numero_contrato}',
            anexo_extensao='pdf',
            tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
        )

    def create_refin_attachment(self) -> None:
        url = self.decoded_response['refinancing_credit_operation']['document_url']
        AnexoContrato.objects.create(
            contrato=self.contract,
            anexo_url=url,
            nome_anexo=f"CCB Gerada pela Financeira - Contrato Refinanciamento {'BYX9' + str(self.contract.id).rjust(10, '0')}",
            anexo_extensao='pdf',
            tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
        )

    def set_first_and_last_due_date(
        self,
        product: Union[Portabilidade, Refinanciamento],
        credit_type: Literal[
            'portability',
            'refinancing',
        ],
    ) -> Union[Portabilidade, Refinanciamento]:
        installments = (
            self.decoded_response.get(f'{credit_type}_credit_operation', {})
            .get('disbursement_options')[0]
            .get('installments')
        )

        first_due_date = installments[0].get('due_date')
        last_due_date = installments[-1].get('due_date')

        product.dt_primeiro_pagamento = datetime.fromisoformat(first_due_date).date()
        product.dt_ultimo_pagamento = datetime.fromisoformat(last_due_date).date()
        product.save(
            update_fields=[
                'dt_primeiro_pagamento',
                'dt_ultimo_pagamento',
            ]
        )
        return product

    def update_portability(self) -> None:
        related_party_key = self.decoded_response['borrower']['related_party_key']
        proposal_key = self.decoded_response['proposal_key']
        self.portability.related_party_key = related_party_key
        self.portability.chave_proposta = proposal_key
        self.portability.chave_operacao = self.decoded_response[
            'portability_credit_operation'
        ]['credit_operation_key']

        self.portability.sucesso_insercao_proposta = True

        self.portability.taxa = (
            self.decoded_response['portability_credit_operation'][
                'disbursement_options'
            ][0]['prefixed_interest_rate']['monthly_rate']
            * 100
        )
        self.portability.save(
            update_fields=[
                'taxa',
                'related_party_key',
                'chave_proposta',
                'chave_operacao',
                'sucesso_insercao_proposta',
            ]
        )

    def update_refinancing(self) -> None:
        related_party_key = self.decoded_response['borrower']['related_party_key']
        proposal_key = self.decoded_response['proposal_key']
        self.refinancing.related_party_key = related_party_key
        self.refinancing.chave_proposta = proposal_key
        self.refinancing.chave_operacao = self.decoded_response[
            'refinancing_credit_operation'
        ]['credit_operation_key']
        self.refinancing.sucesso_insercao_proposta = True
        self.refinancing.save()

    def success_insert_response(self) -> None:
        self.update_portability()
        self.update_refinancing()

        self.set_first_and_last_due_date(
            product=self.portability,
            credit_type='portability',
        )
        self.set_first_and_last_due_date(
            product=self.refinancing,
            credit_type='refinancing',
        )

        self.create_port_attachment()
        self.create_refin_attachment()
        self.set_ccb()
        self.log_success_message()

    def set_ccb(self) -> None:
        self.contract.is_ccb_generated = True
        self.contract.save(update_fields=['is_ccb_generated'])

    def error_response(self) -> None:
        self.error_flag_insert(self.portability)
        self.error_flag_insert(self.refinancing)
        self.log_error_message()

    def error_flag_insert(self, product) -> None:
        product.sucesso_insercao_proposta = False
        product.insercao_sem_sucesso = (
            f"{self.decoded_response['description'], self.decoded_response['code']}"
        )
        product.save()

    def insert_response(self) -> None:
        if self.response.status_code in (200, 201, 202):
            self.success_insert_response()
        else:
            self.error_response()

    def log_success_message(self) -> None:
        message = (
            f'{self.client.id_unico} - Contrato(ID:{self.contract.pk}, PORT + REFIN):'
            f' Proposta inserida na QITECH'
        )
        logger.info(message, extra={'extra': self.decoded_response})

    def log_error_message(self) -> None:
        message = (
            f'{self.client.id_unico} - Contrato(ID: {self.contract.pk}, PORT + REFIN):'
            f' ERRO ao INSERIR PROPOSTA'
        )
        logger.critical(message, extra={'extra': self.decoded_response})
