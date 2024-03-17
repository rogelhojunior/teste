"""Tis module implements the QiTechWebHookDataCanceledPaymentData class."""

import logging

# built-in imports
from logging import Logger
from contract.models.contratos import Refinanciamento
from contract.models.PaymentRefusedIncomingData import PaymentRefusedIncomingData
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.services.payment.payment_resubmission import PaymentResubmission
from contract.services.persistance.logs import create_log_records
from core.constants import EnumTipoConta
from core.models.cliente import DadosBancarios
from custom_auth.models import UserProfile

# local imports
from .QiTechWebhookData import QiTechWebhookData

# constants
PIX = 'pix_refusal'
TED = 'ted_refusal'
STATUS_PAYMENT_FAILED = ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
STATUS_CANCELED = ContractStatus.REPROVADO.value
USER_QITECH = '30620610000159'


class QiTechWebhookPaymentFailedData(QiTechWebhookData):
    def __init__(self, data: dict) -> None:
        super().__init__(data)

        if not self.is_cancel_reason_present():
            raise Exception(
                "cancel_reason is not present in data['data']['cancel_reason']"
            )

        self.cancel_reason = self.get_cancel_reason()
        self.refused_payment_record = None

    def is_cancel_reason_present(self) -> bool:
        try:
            self.get_cancel_reason()
            return True
        except KeyError:
            return False

    def get_cancel_reason(self) -> str:
        return self.data['data']['cancel_reason']

    def is_disbursed_hour_closed(self) -> bool:
        return (
            self.data['data'].get('cancel_reason_enumerator')
            == 'disbursing_hour_closed'
        )

    def process_incoming_data(self) -> None:
        if self.is_pix():
            pass

        elif self.is_ted():
            self.update_product_status(STATUS_PAYMENT_FAILED)
            self.create_status_contract(STATUS_PAYMENT_FAILED)
            self.process_ted_refusal_data()
        elif self.is_disbursed_hour_closed():
            PaymentResubmission(
                product=self.product,
            ).execute()
        else:
            self.update_product_status(STATUS_CANCELED)
            self.create_status_contract(STATUS_CANCELED)

    def is_pix(self) -> bool:
        return self.cancel_reason == PIX

    def is_ted(self) -> bool:
        return self.cancel_reason == TED

    def process_ted_refusal_data(self) -> None:
        self.refused_payment_record = self.create_ted_refused_record()
        self.update_payment_refused_record(self.refused_payment_record)

    def process_pix_refusal_data(self) -> None:
        record = self.create_pix_refused_record()
        self.update_payment_refused_record(record)

    def create_ted_refused_record(self) -> PaymentRefusedIncomingData:
        try:
            bank_data = DadosBancarios.objects.filter(
                cliente=self.client,
                conta_numero=self.extract_account_number(),
                conta_digito=self.extract_account_digit(),
            ).first()
        except DadosBancarios.DoesNotExist:
            bank_data = None

        return PaymentRefusedIncomingData.objects.create(
            reason_id=self.extract_data_from_keys(
                'data', 'ted_refusal', 'reason_enumerator'
            ),
            reason_description=self.extract_data_from_keys(
                'data', 'ted_refusal', 'reason'
            ),
            bank_data=bank_data,
            is_pix=False,
            is_ted=True,
        )

    def extract_account_number(self) -> str:
        account_number = self.extract_data_from_keys(
            'data', 'ted_refusal', 'destination', 'account_number'
        )
        return str(account_number)

    def extract_account_digit(self) -> str:
        account_digit = self.extract_data_from_keys(
            'data', 'ted_refusal', 'destination', 'account_digit'
        )
        return str(account_digit)

    def create_pix_refused_record(self) -> PaymentRefusedIncomingData:
        return PaymentRefusedIncomingData.objects.create(
            reason_id=self.extract_data_from_keys(
                'data', 'ted_refusal', 'reason_enumerator'
            ),
            reason_description=self.extract_data_from_keys(
                'data', 'ted_refusal', 'reason'
            ),
            transaction_key=self.extract_data_from_keys(
                'data', 'ted_refusal', 'transaction_key'
            ),
            is_pix=True,
            is_ted=False,
        )

    def update_payment_refused_record(self, record: PaymentRefusedIncomingData) -> None:
        if self.product.payment_refused_incoming_data is not None:
            self.product.payment_refused_incoming_data.delete()
        self.product.payment_refused_incoming_data = record
        self.product.save()

    def update_product_status(self, status: int) -> None:
        self.product.status = status
        self.product.save()

    def create_status_contract(self, status: int) -> None:
        user = UserProfile.objects.get(identifier=USER_QITECH)
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=status,
            descricao_mesa=f'{self.cancel_reason}',
            created_by=user,
        )

    def log_message(self, logger: Logger) -> None:
        message = f'{self.client.id_unico} - Contrato({self.contract.pk}): pagamento foi cancelado.'
        if self.refused_payment_record is not None:
            message += f' Motivo: {self.refused_payment_record.reason_description}'
        logger.info(message, extra=self.data)

    def execute(self, logger: logging):
        from contract.constants import STATUS_REPROVADOS

        if not StatusContrato.objects.filter(
            contrato=self.contract, nome__in=STATUS_REPROVADOS
        ).exists():
            self.set_contract_records()
            self.process_incoming_data()
            self.create_qi_tech_log_records()
            self.log_message(logger)


class QiTechWebhookPaymentFailedDataRefinancing(QiTechWebhookPaymentFailedData):
    PAYMENT_FAILED_ENUMERATORS = [
        'agencia_conta_invalida',
        'social_security_invalid_disbursement_account',
        'divergencia_titulatidade',
        'conta_destinatario_encerrada',
        'documento_divergente',
    ]

    def __init__(self, data, refinancing: Refinanciamento):
        super().__init__(data)
        self.product = refinancing
        self.contract = self.product.contrato
        self.client = self.contract.cliente
        self.status = self.data.get('data', {}).get('credit_operation_status')

    def process_incoming_data(self) -> None:
        self.update_product_status(STATUS_PAYMENT_FAILED)
        self.create_status_contract(STATUS_PAYMENT_FAILED)
        self.process_ted_refusal_data()

    def get_bank_data(self):
        try:
            bank_data = DadosBancarios.objects.filter(
                cliente=self.client,
                conta_tipo__in=[
                    EnumTipoConta.CORRENTE_PESSOA_FISICA,
                    EnumTipoConta.POUPANCA_PESSOA_FISICA,
                ],
            ).first()
        except DadosBancarios.DoesNotExist:
            bank_data = None
        return bank_data

    def create_ted_refused_record(self) -> PaymentRefusedIncomingData:
        return PaymentRefusedIncomingData.objects.create(
            reason_id=self.extract_data_from_keys(
                'data',
                'cancel_reason_enumerator',
            ),
            reason_description=self.extract_data_from_keys(
                'data',
                'cancel_reason',
            ),
            bank_data=self.get_bank_data(),
            is_pix=False,
            is_ted=True,
        )

    def execute(self):
        from core.admin import STATUS_REPROVADOS

        if not StatusContrato.objects.filter(
            contrato=self.contract, nome__in=STATUS_REPROVADOS
        ).exists():
            reason_enumerator = self.data.get('data', {}).get(
                'cancel_reason_enumerator'
            )
            if reason_enumerator in self.PAYMENT_FAILED_ENUMERATORS:
                self.process_incoming_data()
                create_log_records(
                    client=self.client, data=self.data, log_type=self.status
                )
                self.log_message(logging.getLogger('webhookqitech'))
            elif reason_enumerator == 'disbursing_hour_closed':
                PaymentResubmission(
                    product=self.product,
                ).execute()
            else:
                self.update_product_status(STATUS_CANCELED)
                self.create_status_contract(STATUS_CANCELED)
            self.log_message(logging.getLogger('webhookqitech'))
