"""
This module implements tests for class QiTechOperationDataInterface.
"""
# built in
from copy import deepcopy

# third
from django.test import TestCase

# local
from core.admin_actions.qitech_operation_data_interface import (
    QiTechOperationDataInterface,
)

VALID_DATA = {
    'data': {
        'credit_operation_status': {
            'enumerator': 'settled',  # operation is settled
        },
        'number_of_installments': 3,
        'installments': [
            {
                'present_amount': 10,
                'installment_status': {
                    'enumerator': 'opened',
                },
                'total_amount': 14,
            },
            {
                'present_amount': 20,
                'installment_status': {
                    'enumerator': 'waiting_payment',
                },
                'total_amount': 14,
            },
            {
                'present_amount': 30,
                'installment_status': {
                    'enumerator': 'overdue',
                },
                'total_amount': 14,
            },
        ],
    }
}


class TestQiTechOperationDataInterfaceIsValid(TestCase):
    """Implements tests for QiTechOperationDataInterface.is_valid method"""

    def setUp(self):
        # Set up a sample valid data for testing
        self.valid_data = deepcopy(VALID_DATA)

    # test valid
    def test_with_valid_data(self):
        qi_tech_data_interface = QiTechOperationDataInterface(self.valid_data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

    # invalid installment_status
    def test_with_invalid_installment_status(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment['installment_status'] = 'invalid status'
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing installment_status
    def test_with_missing_installment_status(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment.pop('installment_status')
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid installment_status_enumerator
    def test_with_invalid_installment_status_enumerator(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment['installment_status']['enumerator'] = 'invalid status'
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing installment_status_enumerator
    def test_with_missing_installment_status_enumerator(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment['installment_status'].pop('enumerator')
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing invalid present_amount
    def test_with_invalid_present_amount(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment['present_amount'] = 'invalid'
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing present_amount
    def test_with_missing_present_amount(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment.pop('present_amount')
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing invalid total_amount
    def test_with_invalid_total_amount(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment['total_amount'] = 'invalid'
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # missing total_amount
    def test_with_missing_total_amount(self):
        for i in range(len(self.valid_data['data']['installments'])):
            invalid_data = self.valid_data
            installment = invalid_data['data']['installments'][i]
            installment.pop('total_amount')
            qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
            self.assertFalse(qi_tech_data_interface.is_valid)

    # different total_amount
    def test_with_different_total_amount(self):
        invalid_data = self.valid_data
        installment = invalid_data['data']['installments'][0]
        installment['total_amount'] = 14.001
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # empty installments
    def test_with_empty_installments(self):
        invalid_data = self.valid_data
        invalid_data['data']['installments'] = []
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid installments
    def test_with_invalid_installments(self):
        invalid_data = self.valid_data
        invalid_data['data']['installments'] = 'invalid'
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # missing installments
    def test_with_missing_installments(self):
        invalid_data = self.valid_data
        invalid_data['data'].pop('installments')
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid credit_operation_status
    def test_with_invalid_credit_operation_status(self):
        invalid_data = self.valid_data
        invalid_data['data']['credit_operation_status'] = 'invalid'
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # missing credit_operation_status
    def test_with_missing_credit_operation_status(self):
        invalid_data = self.valid_data
        invalid_data['data'].pop('credit_operation_status')
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid enumerator
    def test_with_invalid_enumerator(self):
        invalid_data = self.valid_data
        invalid_data['data']['credit_operation_status']['enumerator'] = 'invalid'
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # missing enumerator
    def test_with_missing_enumerator(self):
        invalid_data = self.valid_data
        invalid_data['data']['credit_operation_status'].pop('enumerator')
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid number_of_installments
    def test_with_invalid_number_of_installments(self):
        invalid_data = self.valid_data
        invalid_data['data']['number_of_installments'] = 123.123  # can't be float
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

        invalid_data['data']['number_of_installments'] = None  # can't be None
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

        invalid_data['data']['number_of_installments'] = 'invalid'  # can't be str
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # missing number_of_installments
    def test_with_missing_number_of_installments(self):
        invalid_data = self.valid_data
        invalid_data['data'].pop('number_of_installments')
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # invalid data
    def test_with_invalid_data_key(self):
        invalid_data = self.valid_data
        invalid_data['data'] = 'invalid'
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)

    # missing data
    def test_with_missing_data_key(self):
        invalid_data = self.valid_data
        invalid_data.pop('data')
        qi_tech_data_interface = QiTechOperationDataInterface(invalid_data)
        self.assertFalse(qi_tech_data_interface.is_valid)


class TestQiTechOperationDataInterfaceGetData(TestCase):
    """
    Implements tests for QiTechOperationDataInterface.get_total_amount
    method.
    """

    def setUp(self):
        self.data = deepcopy(VALID_DATA)

    def test_get_amount_settled(self):
        # assert valid data
        qi_tech_data_interface = QiTechOperationDataInterface(self.data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

        # assert total_amount
        expected = 10
        actual = qi_tech_data_interface.get_amount_sum()
        self.assertEqual(expected, actual)

    def test_get_amount_not_settled(self):
        self.data['data']['credit_operation_status']['enumerator'] = 'waiting_signature'

        # assert valid data
        qi_tech_data_interface = QiTechOperationDataInterface(self.data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

        # assert total_amount
        expected = 60
        actual = qi_tech_data_interface.get_amount_sum()
        self.assertEqual(expected, actual)

    def test_get_amount_parcial_settled(self):
        self.data['data']['credit_operation_status']['enumerator'] = 'waiting_signature'
        self.data['data']['installments'][0]['installment_status'][
            'enumerator'
        ] = 'paid'

        # assert valid data
        qi_tech_data_interface = QiTechOperationDataInterface(self.data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

        # assert total_amount
        expected = 50
        actual = qi_tech_data_interface.get_amount_sum()
        self.assertEqual(expected, actual)

    def test_get_number_of_installments(self):
        # assert valid data
        qi_tech_data_interface = QiTechOperationDataInterface(self.data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

        # assert total_amount
        expected = 3
        actual = qi_tech_data_interface.get_number_of_installments()
        self.assertEqual(expected, actual)

    def test_get_total_amount(self):
        # assert valid data
        qi_tech_data_interface = QiTechOperationDataInterface(self.data)
        is_valid = qi_tech_data_interface.is_valid
        self.assertTrue(is_valid)

        # assert total_amount
        expected = 14
        actual = qi_tech_data_interface.get_total_amount()
        self.assertEqual(expected, actual)
