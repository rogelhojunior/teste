"""
This module implements QiTechGetter class.
"""

from contract.constants import QI_TECH_ENDPOINTS
from handlers.qitech_api.utils import extract_decoded_content, send_get_to_qi_tech


class QiTechGetter:
    def get(self, endpoint: str) -> dict:
        response = send_get_to_qi_tech(endpoint)
        decoded_content = extract_decoded_content(response)
        return decoded_content

    def get_debt(self, operation_key: str) -> dict:
        endpoint = QI_TECH_ENDPOINTS['debt'] + operation_key
        return self.get(endpoint)

    def get_credit_transfer(self, proposal: str) -> dict:
        endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + proposal
        return self.get(endpoint)

    def get_port_collateral(self, proposal: str):
        return self.get_collateral(proposal, 'portability_credit_operation')

    def get_refin_collateral(self, proposal: str):
        return self.get_collateral(proposal, 'refinancing_credit_operation')

    def get_collateral(self, proposal: str, credit_operation_type: str):
        endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + proposal
        endpoint += '/' + credit_operation_type
        endpoint += '/collateral'
        return self.get(endpoint)
