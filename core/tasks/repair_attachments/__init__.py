"""This file implements the class AttachmentRepairer"""

# built-in
import base64
import logging
import tempfile
from typing import List

# third
from django.conf import settings
from django.test import Client
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

# local
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato
from custom_auth.models import UserProfile
from handlers.converters import get_base64_from_file

# global declarations
logger = logging.getLogger(__name__)


class AttachmentRepairer:
    """
    Implements a command to replace all the corrupted attachments by
    uncorrupted attachments.

    Attributes:
        - contract (str): The contract information or identifier.
        - temp_folder (str): path to the temporary folder where to
            download the attachments.

    """

    def __init__(self, contract: Contrato, user: UserProfile):
        self.contract = contract
        self.user = user
        self.temp_folder = tempfile.mkdtemp()

    def repair(self) -> None:
        """
        Execute the repair.
        """
        uncorrupted_contract = self.find_uncorrupted_contract()

        if uncorrupted_contract.id == self.contract.id:
            logger.info('Contract is not corrupted.')
            return

        atts = uncorrupted_contract.attachments
        atts_to_repair = [att for att in atts if att.anexo_extensao != 'pdf']
        for att in atts_to_repair:
            downloaded_file = att.download(self.temp_folder)
            self.send_overwriter_request(att, downloaded_file)

    def find_uncorrupted_contract(self) -> Contrato:
        """
        Inside one envelope containing corrupted contract always there
        is one contract not corrupted, this function find the uncupted
        contract.

        Args:
            envelope (EnvelopeContratos): envelope to fix.

        Returns:
            Union[Contrato, None]: uncorrupted contract or None.
        """
        envelope = self.contract.envelope
        return envelope.first_contract

    def send_overwriter_request(self, att: AnexoContrato, uncorrupted_file: str):
        """
        This method is used to send a request to overwrite a corrupted
        file with an uncorrupted one.

        Args:
            att (AnexoContrato): The attachment object containing details
                about the file.
            uncorrupted_file (str): The path to the uncorrupted file.

        It builds a request payload with details from the attachment object,
        opens the uncorrupted file, and prepares it for sending. It then
        obtains an authorization token, adds it to the request headers, and
        sends a POST request to the 'api_upload_documentos' endpoint with
        the payload and file.

        Returns:
            response: The server's response to the request.
        """
        # authorize request
        client = Client()
        authorization_token = self.obtain_bearer_token()
        client.defaults['HTTP_AUTHORIZATION'] = authorization_token

        # build request
        data = {
            'anexo_extensao': att.anexo_extensao,
            'nome_anexo': att.nome_anexo,
            'token_envelope': att.contrato.token_envelope,
            'tipo_anexo': att.tipo_anexo,
            'anexo_base64': self.encode_attachment(uncorrupted_file),
        }

        # send request
        endpoint_url = reverse('api_upload_documentos')
        return client.post(endpoint_url, data=data)

    def encode_attachment(self, file_path: str):
        from pathlib import Path

        file_path_object = Path(file_path)
        base64_content, _ = get_base64_from_file(file_path_object)
        return base64_content

    def obtain_bearer_token(self):
        """
        Obtains a bearer token for the request.
        """
        token = AccessToken.for_user(self.user)
        return f'Bearer {token}'
