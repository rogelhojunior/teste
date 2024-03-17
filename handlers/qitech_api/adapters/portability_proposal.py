from typing import TypedDict

from handlers.qitech_api.adapters import QiTechAPIHandlerAdapter, _HTTPMethods
from handlers.qitech_api.dto.portability_proposal.response import PortabilityProposalDTO


class PortabilityProposalEndpointParams(TypedDict):
    proposal_key: str


class PortabilityProposalAdapter(QiTechAPIHandlerAdapter):
    """
    Adapter class for fetching portability proposals from QiTech's API.

    This class extends the QiTechAPIHandlerAdapter to specifically handle
    the retrieval of portability proposals identified by a unique proposal key.

    Methods:
        get_request_payload: Abstract method implementation for payload retrieval.
        adapt: Prepares and executes the API request.
    """

    def __init__(self, endpoint_params: PortabilityProposalEndpointParams):
        """
        Initializes the PortabilityProposalAdapter with a specific proposal key.

        Args:
            endpoint_params (str): The unique key identifying the portability proposal.
        """
        endpoint: str = '/v2/credit_transfer/proposal/{proposal_key}'
        # TODO: Change _HTTPMethods to HTTPMethod from http package in python 3.11
        http_method: _HTTPMethods = 'GET'
        response_validator = PortabilityProposalDTO
        super().__init__(
            endpoint=endpoint,
            endpoint_params=endpoint_params,
            http_method=http_method,
            response_validator=response_validator,
        )

    def get_request_payload(self) -> None:
        """
        Implementation of the abstract method to return the request payload model.

        This method is currently a placeholder as the 'GET' request does not require a payload.
        """
        return None
