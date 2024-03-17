"""
This module implements views to query data from Qi Tech API.
"""

# built-in
import logging

# third
from django.http import HttpRequest
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# local
from contract.constants import QI_TECH_ENDPOINTS
from handlers.qitech_api.utils import extract_decoded_content, send_get_to_qi_tech


def execute_qi_tech_get(endpoint: str) -> Response:
    """
    Execute a GET operation to Qi Tech API using util functions, decode
    response and return a ready to send Response object.
    """
    try:
        response = send_get_to_qi_tech(endpoint)
        decoded_content = extract_decoded_content(response)
        if response.status_code not in (200, 201, 202):
            message = 'Ocorreu um erro ao simular o contrato: '
            message += f'{decoded_content}'
            logging.error(message)

        return Response(data=decoded_content, status=response.status_code)

    except Exception as e:
        logging.error(f'Ocorreu um erro: {e}')
        return Response(data=None, status=500)


class GetAPIQiTech(APIView):
    """
    API endpoint to retrieve details of a QiTech proposal.

    This view defines an endpoint for querying data of a specific proposal
    provided by QiTech. The query is performed using the HTTP GET method.

    Attributes:
        permission_classes (list): Defines the permission classes for the
        endpoint.

    Methods:
        get(request, proposal_key): Returns the details of the specified
        proposal.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, proposal_key: str):
        """
        This method executes an HTTP GET request to retrieve the details of a
        proposal identified by its unique key from QiTech. The response
        includes proposal data formatted in JSON.

        Args:
            request (Request): The HTTP request object.
            proposal_key (str): The unique key of the proposal.

        Returns:
            Response: A Django REST Framework response object
        """
        endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + proposal_key
        return execute_qi_tech_get(endpoint)


class GetDebtAPIQiTech(APIView):
    """
    API endpoint to retrieve details of a QiTech proposal.

    This view defines an endpoint for querying data of a specific debt
    operation provided by QiTech. The query is performed using the HTTP
    GET method.

    Attributes:
        permission_classes (list): Defines the permission classes for the
        endpoint.

    Methods:
        get(request, proposal_key): Returns the details of the specified
        proposal.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, proposal_key: str):
        """
        This method executes an HTTP GET request to retrieve the details of a
        proposal identified by its unique key from QiTech. The response
        includes proposal data formatted in JSON.

        Args:
            request (Request): The HTTP request object.
            proposal_key (str): The unique key of the proposal.

        Returns:
            Response: A Django REST Framework response object
        """

        endpoint = QI_TECH_ENDPOINTS['debt'] + proposal_key
        return execute_qi_tech_get(endpoint)
