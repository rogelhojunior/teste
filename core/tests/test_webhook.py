import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from core.tests.base_test_webhook import BaseTestWebhook


class TestWebhook(BaseTestWebhook, APITestCase):
    def setUp(self):
        """
        Setup all webhook tests.
        Request Factory acts like WSGIRequest object.
        :return:
        """
        self.proposal_key = str(uuid.uuid4())
        self.user = self.get_webhook_user()

    def test_accepted(self):
        """
        Test for accepted webhook with no Error
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_accepted_webhook_data(self.proposal_key),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_canceled(self):
        """
        Test for canceled webhook
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_canceled_webhook_data(self.proposal_key),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_paid(self):
        """
        Test for canceled webhook
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_paid_webhook_data(self.proposal_key),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pending_settlement_confirmation(self):
        """
        Test for canceled webhook
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_pending_settlement_confirmation_webhook_data(
                    self.proposal_key
                ),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retained_settlement_confirmation(self):
        """
        Test for canceled webhook
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_canceled_webhook_data(self.proposal_key),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_settlement_sent(self):
        """
        Test for canceled webhook
        :return:
        """

        response = self.client.post(
            '/api/consig-inss/webhook-qitech/',
            data={
                'encoded_body': self.get_canceled_webhook_data(self.proposal_key),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
