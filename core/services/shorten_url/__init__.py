import sys
from abc import ABC, abstractmethod

# TODO: Remove this after python update to 3.11
if sys.version_info >= (3, 11):
    from http import HTTPMethod
else:
    from core.common.enums import HTTPMethod

from logging import getLogger
from typing import Literal, Optional, Type, TypeAlias

import requests
from pydantic import HttpUrl, ValidationError
from requests import ConnectionError, HTTPError, RequestException, Response, Timeout

from core.dto.services.shorten_url import ResponseModelType
from core.settings import SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS

logger = getLogger(__name__)

RequestAWS3APIModes: TypeAlias = Literal['shorten', 'remove', 'track']


class BaseShortenURL(ABC):
    """
    Abstract base class for implementing URL shortening services.

    This class provides the framework for creating, removing, and tracking shortened URLs.
    It defines common attributes and methods required for a URL shortening service,
    which should be implemented by any subclass.

    Attributes:
        service_url (str): Base URL of the URL shortening service.
        long_url (HttpUrl): The original URL to be shortened.
        expire_hours (int): The number of hours until the shortened URL expires.

    Args:
        long_url (str): The original URL to be shortened.
        expire_hours (int): Expiry duration in hours for the shortened URL.
    """

    def __init__(self, long_url: str, expire_hours: Optional[int] = None) -> None:
        """
        Initializes the BaseShortenURL class with the URL to be shortened and the expiration time.

        Args:
            long_url (str): The URL that needs to be shortened.
            expire_hours (int): The lifespan of the shortened URL in hours.
        """
        self.service_url: str = ''
        self.__api_key: str = self._get_api_key()
        self.long_url: HttpUrl = long_url
        self.expire_hours: int = (
            expire_hours or SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS
        )

    @abstractmethod
    def _get_api_key(self) -> str:
        """
        Abstract method to retrieve the API key for the URL shortening service.

        This method should be implemented by subclasses to provide the necessary API key for authentication.

        Returns:
            str: The API key for the URL shortening service.
        """
        raise NotImplementedError('Define set_api_key in class')

    def _make_request(
        self, method: HTTPMethod, endpoint: RequestAWS3APIModes, body: dict[str, any]
    ) -> Response:
        """
        Executes an HTTP request to the specified endpoint of the AWS3 link shortening API.

        Args:
            method (HTTPMethod): The HTTP method (GET, POST, etc.) for the request.
            endpoint (RequestAWS3APIModes): The specific API endpoint ('shorten', 'remove', or 'track').
            body (dict[str, any]): The request payload.

        Returns:
            Response: The response from the API.

        Raises:
            HTTPError, ConnectionError, Timeout, RequestException: Raised for network or request-related issues.
            Exception: General exception for any other errors encountered during the request.
        """
        # TODO: Remove this after python update to 3.11
        method: Literal[
            'CONNECT',
            'DELETE',
            'GET',
            'HEAD',
            'OPTIONS',
            'PATCH',
            'POST',
            'PUT',
            'TRACE',
        ] = method.value
        url: HttpUrl = f'{self.service_url}/{endpoint}/'
        headers: dict[str, str] = {'x-api-key': self.__api_key}
        response: Response = Response()
        logger.info(
            'Make request to shortening API',
            extra={
                'url': url,
                'method': method,
                'is_headers_none': (not headers),
                'body': body,
            },
        )
        try:
            response: Response = requests.request(
                method=method, url=url, json=body, headers={'x-api-key': self.__api_key}
            )
            response.raise_for_status()
        except (HTTPError, ConnectionError, Timeout, RequestException) as err:
            logger.exception(
                msg=f'Error occurred in call {url}: {err} of URL shortening API',
                extra={
                    'endpoint': url,
                    'headers': headers,
                    'status_code': getattr(response, 'status_code', None)
                    if isinstance(err, HTTPError)
                    else None,
                    'error_type': type(err).__name__,
                },
            )
            raise
        except Exception as err:
            logger.exception(
                msg='Something wrong when calling the URL shortening API',
                extra={
                    'endpoint': url,
                    'headers': headers,
                    'error_type': type(err).__name__,
                },
            )
            raise
        return response

    @staticmethod
    def validate_response_data(
        response: Response, base_model_class: Type[ResponseModelType]
    ) -> Type[ResponseModelType]:
        """
        Validates the response data against a specified Pydantic model.

        Args:
            response (Response): The response object to validate.
            base_model_class (Type[ResponseModelType]): The Pydantic model class for validation.

        Returns:
            Type[ResponseModelType]: An instance of the specified Pydantic model class with the validated data.

        Raises:
            ValidationError: If the response data does not conform to the Pydantic model.
        """
        try:
            return base_model_class(**response.json())
        except ValidationError as ve:
            logger.exception(
                msg='Invalid response format received from URL shortening aws3.link API',
                extra={
                    'error_details': ve.errors(),
                    'invalid_data': response.json(),
                },
            )
            raise

    @abstractmethod
    def get_shortened_data(self) -> Type[ResponseModelType]:
        """
        Abstract method to retrieve data related to the shortened URL.

        This method should be implemented by subclasses to return data specific to the shortened URL.

        Returns:
            Type[ResponseModelType]: Data related to the shortened URL.
        """
        pass

    @abstractmethod
    def get_shortened_url(self) -> str:
        """
        Abstract method to retrieve the shortened URL.

        This method should be implemented by subclasses to return the actual shortened URL.

        Returns:
            str: The shortened URL.
        """
        pass

    @abstractmethod
    def remove_shortened_url(
        self, key: str, custom_domain: str
    ) -> Type[ResponseModelType]:
        """
        Abstract method to remove a shortened URL.

        This method should be implemented by subclasses to handle the removal of a shortened URL.

        Args:
            key (str): The unique key for the shortened URL.
            custom_domain (str): The custom domain associated with the shortened URL.

        Returns:
            Type[ResponseModelType]: Response from the URL shortening service upon successful removal.
        """
        pass

    @abstractmethod
    def track_shortened_url(
        self, key: str, custom_domain: str
    ) -> Type[ResponseModelType]:
        """
        Abstract method to track a shortened URL.

        This method should be implemented by subclasses to return tracking information for a shortened URL.

        Args:
            key (str): The unique key for the shortened URL.
            custom_domain (str): The custom domain associated with the shortened URL.

        Returns:
            Type[ResponseModelType]: Tracking data for the shortened URL.
        """
        pass
