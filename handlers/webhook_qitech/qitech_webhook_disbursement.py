"""Tis module implements the QiTechWebhookDisbursementData class."""

# built-in imports
import logging

from rest_framework.exceptions import ValidationError

from contract.models.contract_disbursement import ContractDisbursementAccount
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile

# local imports
from .QiTechWebhookData import QiTechWebhookData

# constants
PIX_KEY = 'pix_receipt_list'
TED_KEY = 'ted_receipt_list'
USER_QITECH = '30620610000159'


class QiTechWebhookDisbursementData(QiTechWebhookData):
    """
    Class for disbursement data processing.
    Receives a webhook data object in constructor.
    """

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.contract_status = ContractStatus.INT_FINALIZADO.value
        self.payment_data = None
        self.destination = None

    def create_contract_disbursement(self):
        """
        Creates contract disbursement for free margin
        """
        try:
            ContractDisbursementAccount.objects.create(
                free_margin=self.product,
                url=self.payment_data.get('url'),
                amount=self.payment_data.get('amount'),
                transaction_key=self.payment_data.get('transaction_key'),
                origin_transaction_key=self.payment_data.get('origin_transaction_key'),
                destination_name=self.destination.get('name'),
                destination_type=self.destination.get('type'),
                destination_branch=self.destination.get('branch'),
                destination_purpose=self.destination.get('purpose'),
                destination_document=self.destination.get('document'),
                destination_bank_ispb=self.destination.get('bank_ispb'),
                destination_branch_digit=self.destination.get('branch_digit'),
                destination_account_digit=self.destination.get('account_digit'),
                destination_account_number=self.destination.get('account_number'),
                payment_date=self.payment_data.get('timestamp'),
            )
        except Exception as e:
            logger = logging.getLogger('webhookqitech')
            logger.error(f'ERRO WEBHOOK DESEMBOLSO - {e} -{self.data}')
            raise e

    def process_incoming_data(self) -> None:
        """
        Processes incoming data, verify pix and ted.
        """
        from contract.constants import STATUS_REPROVADOS

        if not StatusContrato.objects.filter(
            contrato=self.contract, nome__in=STATUS_REPROVADOS
        ).exists():
            if self.is_pix():
                self.set_payment_data(PIX_KEY)

            elif self.is_ted():
                self.set_payment_data(TED_KEY)
            else:
                raise ValidationError(
                    {
                        'Erro': 'Tipo de pagamento não identificado.',
                    },
                )
            self.create_contract_disbursement()
            self.update_product_status()
            self.create_status_contract()

    def is_pix(self) -> bool:
        """
        Checks if TED_KEY is in data
        Returns: True or False
        """
        return PIX_KEY in self.data.get('data')

    def is_ted(self) -> bool:
        """
        Checks if TED_KEY is in data
        Returns: True or False
        """
        return TED_KEY in self.data.get('data')

    def set_payment_data(self, payment_type_key: str) -> None:
        """
        Set payment data variables f

        Args:
            payment_type_key: pix or ted key

        Returns:

        """
        self.payment_data = self.data.get('data').get(payment_type_key)[0]
        self.destination = self.payment_data.get('destination')

    def update_product_status(self) -> None:
        """
        Updates free margin status
        """
        self.product.status = self.contract_status
        self.product.save()

    def create_status_contract(self) -> None:
        """
        Creates StatusContrato instance
        """
        user = UserProfile.objects.get(identifier=USER_QITECH)
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=self.contract_status,
            descricao_mesa='Desembolso realizado com sucesso',
            created_by=user,
        )

    def log_message(self, logger: logging.Logger) -> None:
        message = f'{self.client.id_unico} - Contrato({self.contract.pk}): foi desembolsado com sucesso.'
        logger.info(message)
