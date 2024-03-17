import jwt

from custom_auth.models import UserProfile


class BaseTestWebhook:
    """
    This class provides methods for generating webhook data related to credit transfer proposals.
    """

    @staticmethod
    def get_webhook_user():
        data = {
            'unique_id': 'a711f8c3-5741-46fa-a1c6-23af757cceaa',
            'identifier': '30620610000159',
            'name': 'qitech',
            'email': 'qitech@qitech.com.br',
            'password': 123,
        }

        return UserProfile.objects.create(
            **data,
        )

    @staticmethod
    def get_base64_data(data: dict) -> str:
        """
        Transforms dict structure into base64 data
        :param data:
        :return:
        """
        return jwt.encode(
            payload=data,
            key='',
        )

    def get_accepted_webhook_data(self, proposal_key: str) -> str:
        """
        Generate webhook data for an accepted credit transfer proposal.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the accepted proposal.
        :rtype: dict
        """

        return self.get_base64_data(
            {
                'data': {
                    'final_due_balance': 5000.00,
                    'original_contract': {
                        'cet': 1.7306,
                        'interest': 2.21,
                        'total_iof': 6.84,
                        'contract_date': '2021-12-17',
                        'last_due_date': '2029-01-07',
                        'final_due_date': '2023-07-20',
                        'first_due_date': '2023-08-07',
                        'amortization_type': None,
                        'final_due_balance': 5000.00,
                        'effective_interest': 2.21,
                        'installment_number': 80,
                        'origin_ispb_number': '33885724',
                        'origin_operation_type': '0202',
                        'corban_document_number': None,
                        'installment_face_value': 250.00,
                        'origin_contract_number': '635967828',
                        'opened_installment_number': 80,
                        'overdue_installment_number': 0,
                    },
                    'portability_number': '202307130000267328685',
                },
                'proposal_key': proposal_key,
                'webhook_type': 'credit_transfer.proposal',
                'event_datetime': '2023-07-20T09:30:24',
                'proposal_status': 'accepted',
            }
        )

    def get_canceled_webhook_data(self, proposal_key: str) -> str:
        """
        Generate webhook data for a canceled credit transfer proposal.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the canceled proposal.
        :rtype: dict
        """
        return self.get_base64_data(
            {
                'webhook_type': 'credit_transfer.proposal',
                'proposal_status': 'canceled',
                'proposal_key': proposal_key,
                'event_datetime': '2022-11-24T15:42:12',
            }
        )

    def get_paid_webhook_data(self, proposal_key: str) -> str:
        """
        Generate webhook data for a paid credit transfer proposal.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the paid proposal.
        :rtype: dict
        """
        return self.get_base64_data(
            {
                'webhook_type': 'credit_transfer.proposal',
                'proposal_key': proposal_key,
                'proposal_status': 'paid',
                'event_datetime': '2022-11-24T15:42:12',
            }
        )

    def get_pending_settlement_confirmation_webhook_data(
        self, proposal_key: str
    ) -> str:
        """
        Generate webhook data for a credit transfer proposal with pending settlement confirmation.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the proposal with pending settlement confirmation.
        :rtype: dict
        """
        return self.get_base64_data(
            {
                'webhook_type': 'credit_transfer.proposal',
                'proposal_key': proposal_key,
                'proposal_status': 'pending_settlement_confirmation',
                'event_datetime': '2022-11-24T15:42:12',
            }
        )

    def get_retained_settlement_confirmation_webhook_data(
        self, proposal_key: str
    ) -> str:
        """
        Generate webhook data for a credit transfer proposal that is retained.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the retained proposal.
        :rtype: dict
        """
        return self.get_base64_data(
            {
                'webhook_type': 'credit_transfer.proposal',
                'proposal_key': proposal_key,
                'proposal_status': 'retained',
                'event_datetime': '2022-11-24T15:42:12',
                'data': {
                    'retained_reason': {
                        'reason': 'issuer_retention',
                        'description': 'Retenção do Cliente',
                    }
                },
            }
        )

    def get_settlement_sent_webhook_data(self, proposal_key: str) -> str:
        """
        Generate webhook data for a credit transfer proposal with settlement sent.

        :param proposal_key: The unique key associated with the proposal.
        :type proposal_key: str
        :return: A dictionary containing webhook data for the proposal with settlement sent.
        :rtype: dict
        """
        return self.get_base64_data(
            {
                'webhook_type': 'credit_transfer.proposal',
                'proposal_key': proposal_key,
                'proposal_status': 'settlement_sent',
                'event_datetime': '2022-11-24T15:42:12',
                'data': {
                    'receipt': {
                        'amount': 1000,
                        'timestamp': '2022-09-14 11:55:31',
                        'description': '237 0001 1000093 1000093-3 59588111000103 - BCO BRADESCO S.A.',
                        'transaction_key': 'ed3e84a2-1628-4f23-8c11-2b2f4656cedf',
                        'origin': {
                            'account_key': 'ed3e84a2-1628-4f23-8c11-2b2f4656cedf',
                            'bank_code': '329',
                            'branch': '0001',
                            'branch_digit': None,
                            'account_number': '1000361',
                            'account_digit': '3',
                            'type': 'checking_account',
                            'name': 'QI SOCIEDADE DE CRÉDITO DIRETO S.A.',
                            'document': '32402502000135',
                        },
                        'destination': {
                            'bank_code': '237',
                            'branch': '0001',
                            'branch_digit': None,
                            'account_number': '1000093',
                            'account_digit': '3',
                            'type': 'checking_account',
                            'name': 'BCO BRADESCO S.A.',
                            'document': '59588111000103',
                            'purpose': 'Saída Liquidação de Portabilidade',
                        },
                    }
                },
            }
        )
