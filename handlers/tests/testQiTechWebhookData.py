"""This module implements tests for QiTechWebhookData class."""

# built in imports
import uuid

# third party imports
from django.db.models import Model
from django.test import TestCase

from api_log.models import LogCliente, QitechRetornos

# local imports
from contract.models.contratos import Portabilidade
from contract.models.PaymentRefusedIncomingData import PaymentRefusedIncomingData
from handlers.webhook_qitech.QiTechWebhookData import (
    CANCELED_STATUS,
    CONTRACT_KEY,
    DEBT_TYPE,
    STATUS_KEYS,
    QiTechWebhookData,
)

# constants
STATUS_KEY = 'status'
WEBHOOK_TYPE_KEY = 'webhook_type'


class TestQiTechWebhookData(TestCase):
    fixtures = ['QiTechWebhookFixtures.json']

    def generate_random_key(self):
        random_uuid = uuid.uuid4()
        return str(random_uuid)

    def setUp(self):
        self.setUpPortability()
        self.contract = self.portability.contrato
        self.client = self.contract.cliente
        self.status_value = CANCELED_STATUS
        self.webhook_type = DEBT_TYPE
        self.data = self.build_qitech_data_simulation()

    def setUpPortability(self):
        self.proposal_key = self.generate_random_key()
        self.portability = Portabilidade.objects.all()[0]
        self.portability.chave_proposta = self.proposal_key
        self.portability.save()

    def build_qitech_data_simulation(self):
        return {
            CONTRACT_KEY: self.proposal_key,
            WEBHOOK_TYPE_KEY: self.webhook_type,
            STATUS_KEY: self.status_value,
            'data': {
                'ted_refusal': {
                    'transaction_key': '16faabfc-3876-437d-a4f6-aae17a1d68c9',
                    'description': '341 0000 000000-7 12345678900 - NOME BENEFICIÁRIO',
                    'origin': {
                        'account_key': 'a1d2dea5-fa90-4676-a125-da355fdc3ed0',
                        'account_number': '00086',
                        'bank_code': '329',
                        'name': 'ACCOUNT TRANSITORY',
                        'type': 'payment_account',
                        'document': '32402502000135',
                        'branch_digit': None,
                        'account_digit': '8',
                        'branch': '0001',
                    },
                    'fee': 0,
                    'reason_enumerator': 'agencia_conta_invalida',
                    'timestamp': '2022-11-07T14:36:05',
                    'amount': 483.6,
                    'reason': 'Agência ou Conta Destinatária do Crédito Inválida',
                    'destination': {
                        'branch': '0000',
                        'account_number': '000000',
                        'name': 'NOME BENEFICIÁRIO',
                        'purpose': 'Crédito em Conta',
                        'type': 'checking_account',
                        'branch_digit': None,
                        'document': '12345678900',
                        'bank_code': '341',
                        'account_digit': '7',
                    },
                },
                'cancel_reason': 'ted_refusal',
            },
        }

    def set_webhook_type(self, value: str) -> None:
        self.data[WEBHOOK_TYPE_KEY] = value

    def set_status(self, value: str) -> None:
        self.data[STATUS_KEY] = value

    def test_successful_initialization(self):
        qi_tech_data = QiTechWebhookData(self.data)

        self.assertEqual(qi_tech_data.portability.chave_proposta, self.proposal_key)
        self.assertEqual(qi_tech_data.client.pk, self.client.pk)
        self.assertEqual(qi_tech_data.contract.pk, self.contract.pk)
        self.assertEqual(qi_tech_data.status_key, STATUS_KEY)
        self.assertEqual(qi_tech_data.type, self.webhook_type)

    def test_unsuccessful_initialization_portability_not_exists(self):
        self.data[CONTRACT_KEY] = ''

        with self.assertRaises(Portabilidade.DoesNotExist):
            QiTechWebhookData(self.data)

    def test_get_status_key_when_exists(self):
        for key in STATUS_KEYS:
            keys_to_remove = remove_element_from_list(STATUS_KEYS, key)
            self.data = remove_keys_from_dict(self.data, keys_to_remove)
            self.data[key] = ''
            qi_tech_data = QiTechWebhookData(self.data)
            self.assertEqual(qi_tech_data.get_status_key(), key)

    def test_get_status_key_when_not_exists(self):
        self.data.pop(STATUS_KEY)
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertIsNone(qi_tech_data.get_status_key())

    def test_does_status_key_exists(self):
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertTrue(qi_tech_data.does_status_key_exists())

        self.data.pop(STATUS_KEY)
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertFalse(qi_tech_data.does_status_key_exists())

    def test_get_status_when_exists(self):
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertTrue(qi_tech_data.does_status_key_exists())

    def test_is_payment_a_failure_when_true(self):
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertTrue(qi_tech_data.is_payment_failure())

    def test_is_payment_a_failure_when_type_condition_is_false(self):
        self.data = self.build_qitech_data_simulation()
        self.set_webhook_type('anything else')
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertFalse(qi_tech_data.is_payment_failure())

    def test_is_payment_a_failure_when_status_condition_is_false(self):
        self.data = self.build_qitech_data_simulation()
        self.set_status('anything else')
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertFalse(qi_tech_data.is_payment_failure())

    def test_is_payment_a_failure_when_status_both_conditions_is_false(self):
        self.data = self.build_qitech_data_simulation()
        self.set_webhook_type('anything else')
        self.set_status('anything else')
        qi_tech_data = QiTechWebhookData(self.data)
        self.assertFalse(qi_tech_data.is_payment_failure())

    def test_create_qitech_log_records(self):
        qi_tech_data = QiTechWebhookData(self.data)
        number_of_client_logs_before = get_number_of_records(LogCliente)
        number_of_qitech_logs_before = get_number_of_records(QitechRetornos)

        qi_tech_data.create_qi_tech_log_records()
        number_of_client_logs_after = get_number_of_records(LogCliente)
        number_of_qitech_logs_after = get_number_of_records(QitechRetornos)
        self.assertEqual(number_of_client_logs_before, number_of_client_logs_after - 1)
        self.assertEqual(number_of_qitech_logs_before, number_of_qitech_logs_after - 1)

    def test_create_payments_refused_record(self):
        qi_tech_data = QiTechWebhookData(self.data)
        number_of_records_before = get_number_of_records(PaymentRefusedIncomingData)

        qi_tech_data.create_payment_refused_record()
        number_of_records_after = get_number_of_records(PaymentRefusedIncomingData)
        self.assertEqual(number_of_records_before, number_of_records_after - 1)

    def test_extract_data_from_keys(self):
        qi_tech_data = QiTechWebhookData(self.data)

        extracted_data = qi_tech_data.extract_data_from_keys('data')
        self.assertIsInstance(extracted_data, dict)

        extracted_data = qi_tech_data.extract_data_from_keys('data', 'ted_refusal')
        self.assertIsInstance(extracted_data, dict)

        extracted_data = qi_tech_data.extract_data_from_keys(
            'data', 'ted_refusal', 'origin', 'branch_digit'
        )
        self.assertIsNone(extracted_data)

        extracted_data = qi_tech_data.extract_data_from_keys(
            'data', 'ted_refusal', 'amount'
        )
        self.assertIsInstance(extracted_data, float)
        self.assertEqual(extracted_data, self.data['data']['ted_refusal']['amount'])


def remove_keys_from_dict(input_dict, keys_to_remove):
    return {key: input_dict[key] for key in input_dict if key not in keys_to_remove}


def remove_element_from_list(input_list, element_to_remove):
    return [item for item in input_list if item != element_to_remove]


def get_number_of_records(model: Model) -> int:
    return len(model.objects.all())
