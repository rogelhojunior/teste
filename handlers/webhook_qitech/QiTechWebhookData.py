"""This module implements the class QiTechWebHookData."""

from api_log.models import LogCliente, QitechRetornos
from contract.models.contratos import MargemLivre

CONTRACT_KEY = 'key'
DEBT_TYPE = 'debt'
CANCELED_STATUS = 'canceled'
STATUS_KEY = 'status'
WEBHOOK_TYPE_KEY = 'webhook_type'
DISBURSED_STATUS = 'disbursed'


class QiTechWebhookData:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.type = self.data.get(WEBHOOK_TYPE_KEY)
        self.status = self.data.get(STATUS_KEY)
        self.product = None
        self.contract = None
        self.client = None

    def does_status_exists(self) -> bool:
        return self.status is not None

    def is_payment_failure(self) -> bool:
        is_debt_type = self.type == DEBT_TYPE
        is_status_canceled = self.status == CANCELED_STATUS
        return is_debt_type and is_status_canceled

    def is_portability_refinancing_canceled(self):
        is_credit_operation = self.type == 'credit_transfer.proposal.credit_operation'
        status = self.data.get('data', {}).get('credit_operation_status')
        is_refinancing = (
            self.data.get('data', {}).get('credit_operation_type') == 'refinancing'
        )

        is_status_canceled = status == CANCELED_STATUS
        return is_credit_operation and is_status_canceled and is_refinancing

    def is_disbursed_debt(self) -> bool:
        is_debt_type = self.type == DEBT_TYPE
        is_status_disbursed = self.status == DISBURSED_STATUS
        return is_debt_type and is_status_disbursed

    def set_contract_records(self) -> None:
        self.product = MargemLivre.objects.get(chave_proposta=self.data[CONTRACT_KEY])
        self.contract = self.product.contrato
        self.client = self.contract.cliente

    def create_qi_tech_log_records(self) -> None:
        client_log, _ = LogCliente.objects.get_or_create(cliente=self.client)
        QitechRetornos.objects.create(
            log_api_id=client_log.pk,
            cliente=self.client,
            retorno=self.data,
            tipo=self.status,
        )

    def extract_data_from_keys(self, *keys) -> str:
        try:
            data = self.data
            for key in keys:
                data = data[key]
        except KeyError as e:
            keys_chunked = '.'.join(keys)
            message = f'Invalid incoming data. Keys "{keys_chunked}" not present.'
            raise Exception(message) from e
        return data
