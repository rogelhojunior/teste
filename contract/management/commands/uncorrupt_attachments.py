"""This file implements the class Command, this class is responsible to
execute the command uncorrupt_attachments"""

import os
import sys
import tempfile

# built-in
from collections import namedtuple
from typing import List, Union

# third
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from django.test import Client
from django.urls import reverse
from rest_framework.exceptions import AuthenticationFailed

from contract.constants import EnumContratoStatus
from contract.models.anexo_contrato import AnexoContrato
from contract.models.anexo_contrato.anexo_contrato_amazon_s3_interface import (
    AnexoContratoAmazonS3Interface,
)

# local
from contract.models.contratos import Contrato
from contract.models.envelope_contratos import EnvelopeContratos

# global declarations
NotReplacedAtt = namedtuple('NotReplacedAtt', ['att', 'reason'])


class Command(BaseCommand):
    """
    Implements a command to replace all the corrupted attachments by
    uncorrupted attachments.

    Attributes:
        - temp_folder (str): path to the temporary folder where to
            download the attachments.
        - replaced_attachments (List[AnexoContrato]): the attachments
            records that was successfully replaced.
        - not_replaced_attachments (List[NotReplacedAtt (namedtuple))]:
            A list of named tuples representing an attachment that was
            not replaced, with fields 'att' (AnexoContrato) and 'reason'
            (str).
        - user_identifier (str): The user's identifier or username to get
            the authorization in the API
        - user_password (str): The above user's password.
        - contract (str): The contract information or identifier.

    """

    help = 'Search for all corrupted files and then fix them.'
    help += ' Example: python manage.py uncorrupt_attachments '
    help += '<api_user> <api_password> [<contract_id>]'

    def add_arguments(self, parser):
        """
        This method is used to specify the arguments that this command
        expects.

        Args:
            parser (argparse.ArgumentParser): An ArgumentParser instance
            to which the arguments should be added.

        The following arguments are added:
            - 'api_user': A positional argument for the API user. This
                argument is required and should be a string.
            - 'api_password': A positional argument for the API password.
                This argument is required and should be a string.
            - 'contract': An optional positional argument for the contract.
                This argument should be a string. If not provided, it defaults
                to None.
        """
        parser.add_argument('api_user', type=str)
        parser.add_argument('api_password', type=str)
        parser.add_argument('contract', type=int, nargs='?', default=None)

    def handle(self, *args, **options):
        """
        Execute the command.
        """

        # save received args
        self.user_identifier = options['api_user']
        self.user_password = options['api_password']
        self.contract = options['contract']

        # create temp folder to download files
        self.temp_folder = tempfile.mkdtemp()

        # create variables to store log data
        self.replaced_attachments = []
        self.not_replaced_attachments = []

        # find corrupted attachments
        self.corrupted_attachments = self.find_corrupted_attachments()
        for att in self.corrupted_attachments:
            self.fix_attachment(att)

        self.display_data()

    def find_corrupted_attachments(self) -> List[Contrato]:
        """
        Find all the corrupted attachments associated with active
        Contrato records.

        Returns:
            List[AnexoContrato]: corrupted attachments.
        """
        corrupted_attachments = []
        for contract in self.contracts_to_search():
            corrupted_attachments.extend(
                self.find_contract_corrupted_attachments(contract)
            )
        return corrupted_attachments

    def contracts_to_search(self) -> List[Contrato]:
        """
        Determines the contracts to be searched based on the instance's
        contract attribute.

        If the instance has a specific contract assigned, it returns a
        list containing only that contract (if it's active). Otherwise,
        it returns a list of all active contracts.

        Returns:
            List[Contrato]: A list of contracts to be searched.
        """
        if not self.contract:
            return get_active_contracts()
        contract = Contrato.objects.get(id=self.contract)
        return [contract] if contract.is_active else []

    def find_contract_corrupted_attachments(
        self, contract: Contrato
    ) -> List[AnexoContrato]:
        """
        Checks if records AnexoContrato associated with the given
        Contrato record are corrupted.

        Args:
            contract (Contrato): the Contrato record to check.

        Returns:
            List[AnexoContrato]: a list of AnexoContrato records that
                are corrupted.
        """
        return [
            anexo_contrato
            for anexo_contrato in contract.attachments
            if self.attachment_is_corrupted(anexo_contrato)
        ]

    def attachment_is_corrupted(self, att: AnexoContrato) -> bool:
        """
        Checks if the given AnexoContrato record is corrupted.

        Args:
            att (AnexoContrato): the AnexoContrato record to check.

        Returns:
            bool: True if the attachment is corrupted, False otherwise.
        """
        # TODO: how to identify corrupted attachments?
        return True

    def obtain_bearer_token(self):
        """
        This method is used to obtain a bearer token for API authentication.

        It creates a new client, defines the endpoint for token authentication,
        and sends a POST request with the user's identifier and password as payload.

        The method then extracts the 'access' field from the JSON response, which is the bearer token.

        Returns:
            str: The bearer token for API authentication.

        Raises:
            AuthenticationFailed: if the request fails.
        """
        # build request
        endpoint = '/api/auth/token/'
        payload = {'identifier': self.user_identifier, 'password': self.user_password}

        # send request
        response = Client().post(endpoint, payload)
        if response.status_code != 200:
            raise AuthenticationFailed

        return response.json().get('access')

    def fix_attachment(self, att: AnexoContrato):
        """
        Fix a corrupted attachment.

        Args:
            att (AnexoContrato): attachment to fix.
        """
        uncorrupted_file = self.find_and_download_uncorrupted_file(att)
        response = self.send_overwriter_request(att, uncorrupted_file)

        message = ''
        if response.status_code == 200:
            message = f'Attachment {att.nome_anexo} successfully replaced.\n'
        else:
            message = f'Attachment {att.nome_anexo} not replaced.\n'
        sys.stdout.write(message)

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
        token_header = f'Bearer {authorization_token}'
        client.defaults['HTTP_AUTHORIZATION'] = token_header

        # build request
        data = {
            'anexo_extensao': att.anexo_extensao,
            'nome_anexo': att.nome_anexo,
            'token_envelope': att.contrato.token_envelope,
            'tipo_anexo': att.tipo_anexo,
        }

        # send request
        endpoint_url = reverse('api_upload_documentos')
        files_data = self.build_request_files_data(uncorrupted_file, att)
        return client.post(endpoint_url, data=data, files=files_data)

    def build_request_files_data(self, path: str, att: AnexoContrato) -> dict:
        """
        Builds a dictionary containing file data for a request.

        Args:
            path (str): The path to the file to be included in the request.
            att (AnexoContrato): An instance of AnexoContrato representing
                the attachment.

        Returns:
            dict: A dictionary containing the file data.
        """
        files = None
        with open(path, 'rb') as file:
            files = {
                'arquivo': (
                    att.name_with_extension,
                    file,
                    f'application/{att.anexo_extensao}',
                )
            }
        return files

    def find_and_download_uncorrupted_file(self, att: AnexoContrato) -> str:
        """
        Find the uncorrupted file associated with the given corrupted
        attachment, and download it.

        Args:
            att (AnexoContrato): the corrupted attachment.

        Returns:
            str: the path to the downloaded file.
        """
        envelope = att.contrato.envelope
        uncorrupted_contract = self.find_uncorrupted_contract(envelope)
        uncorrupted_att = self.get_contract_att_by_name(
            contract=uncorrupted_contract,
            att_name=att.nome_anexo,
        )
        return self.download_attachment(uncorrupted_att)

    def find_uncorrupted_contract(
        self, envelope: EnvelopeContratos
    ) -> Union[Contrato, None]:
        """
        Inside one envelope containing corrupted contract always there
        is one contract not corrupted, this function find the uncupted
        contract.

        Args:
            envelope (EnvelopeContratos): envelope to fix.

        Returns:
            Union[Contrato, None]: uncorrupted contract or None.
        """
        return envelope.first_contract

    def download_attachment(self, att_record: AnexoContrato) -> str:
        """
        Download an attachment from storage server (S3).

        Args:
            att (AnexoContrato): the attachment record storing
                information about the file to be downloaded.

        Returns:
            str: the path to the file that was downloaded
        """
        s3_interface = AnexoContratoAmazonS3Interface(att_record)
        destination_path = os.path.join(
            self.temp_folder, att_record.name_with_extension
        )
        s3_interface.download_file_from_s3(destination_path)
        return destination_path

    def get_contract_att_by_name(
        self, contract: Contrato, att_name: str
    ) -> AnexoContrato:
        """
        Get the object AnexoContrato in the target contract, using the
        record it-self and the field 'nome_anexo'.

        Args:
            contract (Contrato): target contract.
            att_name (str): target contract's attachment name.

        Returns:
            AnexoContrato: target attachment.
        """
        target_attachment_query = AnexoContrato.objects.filter(
            contrato=contract,
            nome_anexo=att_name,
        )
        self.validade_target_attachment_query(target_attachment_query)
        return target_attachment_query.first()

    def validade_target_attachment_query(self, query: QuerySet) -> None:
        """
        Validate target contract attachment query results, raising an
        exception when invalid.

        Args:
            query(QuerySet): the resulting query.

        Raises:
            AnexoContrato.DoesNotExist: if there is no attachment with
                with same name from source contract to target contract.
            AnexoContrato.MultipleObjectsReturned: if there are multiple
                attachments with the same name.
        """
        if not query.exists():
            raise AnexoContrato.DoesNotExist

        if len(query) > 1:
            raise AnexoContrato.MultipleObjectsReturned

    def display_data(self):
        """
        Display information about corrupted contracts, envelopes, and
        attachment replacements.

        This function writes statistics regarding corrupted contracts
        and attachment replacements to the standard output. It provides
        information on the number of corrupted contracts found, the
        total number of envelopes they are associated with, the count of
        attachments successfully replaced, and the count of attachments
        that were not replaced.

        Example of output:
            Corrupted Attachments Found: 14
            Attachments Successfully Replaced: 12
            Attachments Not Replaced: 2
        """
        num_corrupted_attachments = len(self.corrupted_attachments)
        num_successful_replacements = len(self.replaced_attachments)
        num_not_replaced = len(self.not_replaced_attachments)

        # Write the statistics to the standard output
        sys.stdout.write(f'Corrupted Attachments Found: {num_corrupted_attachments}\n')
        sys.stdout.write(
            f'Attachments Successfully Replaced: {num_successful_replacements}\n'
        )
        sys.stdout.write(f'Attachments Not Replaced: {num_not_replaced}\n')
        sys.stdout.flush()


def get_contract_list_envelopes(contracts: List[Contrato]) -> List[EnvelopeContratos]:
    """
    Receive a list of Contrato records and return the corresponding
    EnvelopeContratos records without duplicates.

    Args:
        contracts: List of Contrato records

    Returns:
        List[EnvelopeContratos]: list of EnvelopeContratos records.
    """
    tokens = [contract.token_envelope for contract in contracts]
    unique_tokens = list(set(tokens))
    return [
        EnvelopeContratos.objects.get(token_envelope=token) for token in unique_tokens
    ]


def get_active_contracts() -> List[Contrato]:
    """
    Get all active Contrato records.

    Returns:
        List[Contrato]: list of Contrato records.
    """

    return Contrato.objects.filter(
        status__in=(
            EnumContratoStatus.DIGITACAO,
            EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
            EnumContratoStatus.FORMALIZADO,
            EnumContratoStatus.MESA,
            EnumContratoStatus.EM_AVERBACAO,
        )
    )
