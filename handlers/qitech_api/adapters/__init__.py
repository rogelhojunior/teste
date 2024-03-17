import locale
from abc import ABC, abstractmethod
from datetime import datetime
from logging import getLogger
from typing import Literal, Optional, Type, TypeVar, Union
from uuid import UUID

import jwt
import requests
from pydantic import BaseModel, HttpUrl, ValidationError
from requests import ConnectionError, HTTPError, RequestException, Response, Timeout

from core import settings

logger = getLogger(__name__)
QITechResponseModelType = TypeVar('QITechResponseModelType', bound=BaseModel)
QITechRequestModelType = TypeVar('QITechRequestModelType', bound=BaseModel)
# TODO: Remove this in python 3.11
_HTTPMethods = Literal[
    'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH'
]


class RequestParams(BaseModel):
    method: str
    url: HttpUrl
    params: Optional[Union[dict, list, tuple, bytes]] = None
    data: Optional[Union[dict, list, tuple, bytes]] = None
    json_: Optional[dict] = None
    headers: Optional[dict[str, str]] = None
    cookies: Optional[dict] = None
    files: Optional[dict] = None
    auth: Optional[tuple[str, str]] = None
    timeout: Optional[Union[float, tuple[float, float]]] = None
    allow_redirects: Optional[bool] = True
    proxies: Optional[dict[str, str]] = None
    verify: Union[bool, str] = True
    stream: Optional[bool] = None
    cert: Optional[Union[str, tuple[str, str]]] = None

    def to_dict(self) -> dict[str, any]:
        return self.model_dump(exclude_none=True)


class QiTechAPIHandlerAdapter(ABC):
    """
    Abstract base class for handling API interactions with QiTech's services.

    This class provides a structured approach to constructing and executing
    API requests, including secure header generation, request building,
    and response decoding and validation. It is designed to be extended
    by subclasses that implement specific API interactions.

    Attributes:
        base_url (HttpUrl): The base URL for the QiTech API.
        __api_key (UUID): The API key for authenticating with the QiTech API.
        __client_private_key (str): The private key for client-side encryption.
        __decryption_key (str): The decryption key for decrypting API responses.
        request_params (RequestParams): The parameters for the API request.
        response (Response): The response object from the API request.

    Methods:
        __init__: Constructor for initializing API handler with specific endpoint and method.
        adapt: Abstract method to adapt the handler to specific API requests.
        get_request_payload: Abstract method to retrieve the request payload model.
        build_response: Constructs and executes an API request.
        get_response_data: Retrieves and validates the API response data.
        __generate_encrypted_header: Generates encrypted headers for API requests.
        __decode_response: Decodes encrypted response data from the API.
        __make_request: Sends the API request with the specified parameters.
        __validate_decoded_response: Validates the decoded response against the expected schema.
    """

    base_url: HttpUrl = settings.QITECH_BASE_ENDPOINT_URL
    __api_key: UUID = settings.QITECH_INTEGRATION_KEY
    __client_private_key: str = settings.QITECH_CLIENT_PRIVATE_KEY
    __decryption_key: str = ''
    request_params: RequestParams
    response: Response

    def __init__(
        self,
        endpoint: str,
        endpoint_params: dict[str, any],
        # TODO: Change _HTTPMethods to HTTPMethod from http package in python 3.11
        http_method: _HTTPMethods,
        response_validator: Type[QITechResponseModelType],
        request_validator: Optional[Type[QITechRequestModelType]] = None,
    ):
        """
        Initializes the API handler with specific endpoint details.

        Args:
            endpoint (str): The endpoint URL for the API request.
            endpoint_params (dict[str, any]): Parameters to format the endpoint URL.
            http_method (_HTTPMethods): The HTTP method for the API request.
            response_validator (Type[QITechResponseModelType]): Validator for the API response.
            request_validator (Optional[Type[QITechRequestModelType]]): Validator for the API request payload.
        """
        self.endpoint: str = endpoint
        self.endpoint_params: dict[str, any] = endpoint_params
        self.set_formatted_endpoint()

        # TODO: Change _HTTPMethods to HTTPMethod from http package in python 3.11
        self.http_method: _HTTPMethods = http_method
        self.response_validator: Type[QITechResponseModelType] = response_validator
        self.request_validator: Type[QITechRequestModelType] = request_validator

    def set_formatted_endpoint(self):
        self.endpoint: str = self.endpoint.format(**self.endpoint_params)

    def adapt(self) -> None:
        """
        Prepares and executes the API request.

        This method should be implemented by subclasses to define specific
        request preparations and executions.
        """
        self.request_params: RequestParams = RequestParams(
            method=self.http_method,
            url=f'{self.base_url}{self.endpoint}',
            json=self.get_request_payload(),
        )
        self.response: Response = self.build_response(
            request_params=self.request_params
        )

    @abstractmethod
    def get_request_payload(self) -> Type[QITechRequestModelType]:
        """
        Abstract method to return the request payload model.

        Subclasses should implement this method to provide the payload model
        for the API request.

        Returns:
            Type[QITechRequestModelType]: The request payload model type.
        """
        raise NotImplementedError(
            'The Adapter requires the get_request_payload function to be implemented.'
        )

    def build_response(self, request_params: RequestParams) -> Response:
        """
        Constructs and executes an API request based on the provided parameters.

        Args:
            request_params (RequestParams): Parameters for constructing the API request.

        Returns:
            Response: The response from the API request.
        """
        body = request_params.json_ or request_params.data or ''
        request_params.headers = self.__generate_encrypted_header(
            method=request_params.method,
            endpoint_formatted=self.endpoint,
            body=body,
        )
        return self.__make_request(request_params=request_params)

    def get_response_data(self) -> QITechResponseModelType:
        """
        Retrieves and validates the API response data.

        Processes the API response and validates it against the specified response model.

        Returns:
            QITechResponseModelType: The validated and processed response data.
        """
        decoded_response = self.__decode_response(response_data=self.response.json())
        return self.__validate_decoded_response(
            decoded_response=decoded_response,
            response_validator=self.response_validator,
        )

    @classmethod
    def __generate_encrypted_header(
        cls, method: str, endpoint_formatted: str, body: Optional[str | dict] = ''
    ) -> dict[str, any]:
        """
        Generates encrypted headers for secure API requests.

        Args:
            method (str): The HTTP method used for the request.
            endpoint_formatted (str): The formatted endpoint URL for the request.
            body (Optional[str | dict]): The request body, default is empty.

        Returns:
            dict[str, any]: A dictionary containing the necessary headers for the API request.
        """
        locale.setlocale(category=locale.LC_ALL, locale='en_US.UTF-8')
        date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        content_type = 'application/json'

        string_to_sign = (
            f'{method}\n{body}\n{content_type}\n{date}\n{endpoint_formatted}'
        )
        claims = {'sub': cls.__api_key, 'signature': string_to_sign}
        encoded_header_token = jwt.encode(
            claims, cls.__client_private_key, algorithm='ES512'
        )
        authorization = f'QIT {cls.__api_key}:{encoded_header_token}'

        return {
            'AUTHORIZATION': authorization,
            'API-CLIENT-KEY': cls.__api_key,
        }

    @classmethod
    def __decode_response(cls, response_data: dict[str, any]) -> dict[str, any]:
        """
        Decodes the encrypted response data from the API.

        Args:
            response_data (dict[str, any]): The response data from the API.

        Returns:
            dict[str, any]: The decoded response data.

        Raises:
            ValueError: If the encoded body is not found in the response.
        """
        encoded_body = response_data.get('encoded_body')
        print(response_data.keys())
        if not encoded_body:
            raise ValueError('Encoded body not found in response')

        return jwt.decode(
            encoded_body,
            key=cls.__decryption_key,
            options={'verify_signature': False},
        )

    @classmethod
    def __make_request(cls, request_params: RequestParams) -> Response:
        """
        Makes an HTTP request to the specified URL with the given parameters.

        Args:
            request_params (RequestParams): Parameters for the API request.

        Returns:
            Response: The response object from the API request.

        Raises:
            HTTPError, ConnectionError, Timeout, RequestException: For request-related errors.
            Exception: For any unexpected errors that occur.
        """
        try:
            response = requests.request(**request_params.to_dict())
            response.raise_for_status()
            return response
        except (HTTPError, ConnectionError, Timeout, RequestException) as err:
            logger.exception(f'Error occurred in call {request_params.url}: {err}')
            raise
        except Exception:
            logger.exception('Unexpected error occurred')
            raise

    @staticmethod
    def __validate_decoded_response(
        decoded_response: dict[str, any],
        response_validator: QITechResponseModelType,
    ) -> QITechResponseModelType:
        """
        Validates the decoded response data against the specified schema.

        Args:
            decoded_response (dict[str, any]): Decoded response data to be validated.
            response_validator (Type[QITechResponseModelType]): Validator for the response model.

        Returns:
            QITechResponseModelType: The validated response data.

        Raises:
            ValidationError: If the decoded response does not conform to the expected schema.
        """
        try:
            return response_validator.model_validate(decoded_response)
        except ValidationError as e:
            logger.exception(
                f'Validation error from base model {response_validator.__class__.__name__}: {e.errors()}'
            )
            raise
