"""This module implements UnicoRequest class."""

# built-in
import json

from rest_framework.request import Request
from rest_framework.response import Response

# thirds
from rest_framework.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

# local
from contract.models.envelope_contratos import EnvelopeContratos

from .unico_score_contract_validator import (
    APPROVED_SCORE_RANGE,
    DISAPPROVED_SCORE_RANGE,
    RESTRICTIVE_ERROR_SCORE_RANGE,
    UNICO_DIVERGENCY_STATUS,
    UNICO_SCORE_SUCCESS_STATUS,
    UnicoScoreContractValidator,
)


class UnicoRequestProcessor:
    """
    This class abstracts the request incoming fro UNICO, containing the
    status and score of the previous generated selfie.

    Attributes:
        request (rest_framework.request.Request): the incoming request.
        data (dict): the serialized data inside the request.
        envelope (EnvelopeContratos): the envelope referred by data.id
            keys inside incoming request data.
    """

    def __init__(self, request: Request) -> None:
        self.request = request
        self.data = self.decode_data()
        self.validate_data()
        self.envelope = self.get_envelope()

    @property
    def id_processo(self) -> str:
        try:
            return self.data['data']['id']
        except KeyError:
            return None

    @property
    def status(self) -> str:
        try:
            return self.data['data']['status']
        except KeyError:
            return None

    @property
    def score(self) -> str:
        try:
            return self.data['data']['score']
        except KeyError:
            return None

    def decode_data(self) -> dict:
        """
        Decode the request data.

        Returns:
            dict: request body data.
        """
        data = self.request.body.decode('utf-8')
        return json.loads(data)

    def get_envelope(self) -> EnvelopeContratos:
        """Get envelope using property id_processo"""
        return EnvelopeContratos.objects.get(id_processo_unico=self.id_processo)

    def validate_data(self) -> None:
        """Validate the incoming data. If not valid raises an exception."""
        self.validate_status()
        self.validate_score()
        self.validate_id_processo()

    def validate_status(self) -> None:
        """Validate the incoming status. If not valid raises an exception."""
        if self.status not in (
            UNICO_DIVERGENCY_STATUS,
            UNICO_SCORE_SUCCESS_STATUS,
        ):
            raise UnicoInvalidRequest(f'Invalid status: {self.status}')

    def validate_score(self) -> None:
        """Validate the incoming score. If not valid raises an exception."""
        if self.score:
            for score_range in (
                RESTRICTIVE_ERROR_SCORE_RANGE,
                DISAPPROVED_SCORE_RANGE,
                APPROVED_SCORE_RANGE,
            ):
                if self.score in score_range:
                    break
            else:
                message = f'Invalid score: {self.score}. Out of range'
                raise UnicoInvalidRequest(message)

    def validate_id_processo(self) -> None:
        """Validate the incoming data. If not valid raises an exception."""
        if self.id_processo is None:
            raise UnicoInvalidRequest('Invalid id_processo: does not exist.')

        envelope_exists = EnvelopeContratos.objects.filter(
            id_processo_unico=self.id_processo
        ).exists()
        if not envelope_exists:
            message = 'Invalid id_processo: does not match any envelope.'
            raise UnicoInvalidRequest(message)

    def process_request(self) -> None:
        """Process the incoming request."""
        self.save_data_on_envelope()
        for contract in self.envelope.contracts:
            if contract.contrato_assinado:
                UnicoScoreContractValidator(contract).validate()

    def save_data_on_envelope(self) -> None:
        """Save incoming score on envelope record."""
        self.envelope.score_unico = self.score
        self.envelope.status_unico = self.status
        self.envelope.save()

    def make_success_response(self) -> Response:
        """
        Generate success response for this request.

        Returns
            Response: the response for the request.
        """
        return Response(
            {'Sucesso': 'Score dos Contratos Validados Com sucesso.'}, HTTP_200_OK
        )

    def make_error_response(self) -> Response:
        """
        Generate error response for this request.

        Returns
            Response: the response for the request.
        """
        return Response(
            {'Erro': 'Não foi possível encontrar o contrato.'},
            HTTP_500_INTERNAL_SERVER_ERROR,
        )


class UnicoInvalidRequest(Exception):
    """Raises this exception when a not valid UNICO request is received."""
