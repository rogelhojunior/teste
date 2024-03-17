import sys

# TODO: Remove this after python update to 3.11
if sys.version_info >= (3, 11):
    from http import HTTPMethod
else:
    from core.common.enums import HTTPMethod


from logging import getLogger
from typing import Optional, Type

from requests import Response

from core.dto.services.shorten_url.create import (
    ShortenUrlBodyDTO,
    ShortenUrlResponseDTO,
)
from core.dto.services.shorten_url.remove import (
    RemoveShortenUrlBodyDTO,
    RemoveURLResponseDTO,
)
from core.dto.services.shorten_url.track import (
    TrackShortenUrlBodyDTO,
    TrackShortenUrlResponseDTO,
)
from core.services.shorten_url import BaseShortenURL
from core.settings import (
    AWS3_LINK_SHORTENER_API_KEY,
    SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS,
)

logger = getLogger(__name__)


class AWS3LinkShortURLService(BaseShortenURL):
    """
    Service class for interacting with the AWS3 link shortening API.

    This class extends the BaseShortenURL to provide specific functionalities for creating, removing,
    and tracking shortened URLs using the AWS3 service.

    Attributes:
        shortened_data (Optional[Type[ShortenUrlResponseDTO]]): Stores the data of the shortened URL.

    Args:
        long_url (str): The original URL to be shortened.
        expire_hours (int): The number of hours until the shortened URL expires.
        custom_key (Optional[str]): A custom key for the shortened URL.
        key_length (Optional[int]): The length of the key for the shortened URL.
        custom_domain (Optional[str]): A custom domain for the shortened URL.
    """

    shortened_data: Optional[Type[ShortenUrlResponseDTO]] = None

    def __init__(
        self,
        long_url: str,
        expire_hours: Optional[int] = None,
        custom_key: Optional[str] = None,
        key_length: Optional[int] = None,
        custom_domain: Optional[str] = None,
    ) -> None:
        """
        Initializes the AWS3LinkShortURLService with the specified parameters.

        Args:
            long_url (str): The URL that needs to be shortened.
            expire_hours (Optional[int]): The lifespan of the shortened URL in hours.
            custom_key (Optional[str]): Custom key for the shortened URL.
            key_length (Optional[int]): Length of the key for the shortened URL.
            custom_domain (Optional[str]): Custom domain for the shortened URL.
        """
        super().__init__(
            long_url=long_url,
            expire_hours=expire_hours or SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS,
        )
        self.service_url: str = 'https://api.aws3.link'

        self.custom_key: Optional[str] = custom_key
        self.key_length: Optional[int] = key_length
        self.custom_domain: Optional[str] = custom_domain

    def _get_api_key(self) -> str:
        """
        Retrieves the API key for the AWS3 link shortening service.

        Returns:
            str: The API key for the AWS3 service.
        """
        return AWS3_LINK_SHORTENER_API_KEY

    def get_shortened_data(self) -> Type[ShortenUrlResponseDTO]:
        """
        Retrieves data related to the shortened URL from the AWS3 service.

        Returns:
            Type[ShortenUrlResponseDTO]: Data of the shortened URL.
        """
        shorten_url_body = ShortenUrlBodyDTO(
            longUrl=self.long_url,
            expireHours=self.expire_hours,
            customKey=self.custom_key,
            keyLength=self.key_length,
            customDomain=self.custom_domain,
        )
        response: Response = self._make_request(
            method=HTTPMethod.POST, endpoint='shorten', body=shorten_url_body.to_dict()
        )

        self.shortened_data = self.validate_response_data(
            response=response, base_model_class=ShortenUrlResponseDTO
        )
        return self.shortened_data

    def get_shortened_url(self) -> str:
        """
        Retrieves the shortened URL.

        Returns:
            str: The shortened URL.
        """
        if self.shortened_data:
            return str(self.shortened_data.shortUrl)
        return str(self.get_shortened_data().shortUrl)

    def remove_shortened_url(
        self, key: str, custom_domain: str
    ) -> Type[RemoveURLResponseDTO]:
        """
        Removes a shortened URL from the AWS3 service.

        Args:
            key (str): The unique key identifying the shortened URL.
            custom_domain (str): The custom domain associated with the shortened URL.

        Returns:
            Type[RemoveURLResponseDTO]: Response from the service upon successful removal.
        """
        remove_shorten_url_body = RemoveShortenUrlBodyDTO(
            key=key, custom_domain=custom_domain
        )
        response: Response = self._make_request(
            method=HTTPMethod.DELETE,
            endpoint='remove',
            body=remove_shorten_url_body.to_dict(),
        )

        return self.validate_response_data(
            response=response, base_model_class=RemoveURLResponseDTO
        )

    def track_shortened_url(
        self, key: str, custom_domain: str
    ) -> Type[TrackShortenUrlResponseDTO]:
        """
        Tracks a shortened URL using the AWS3 service.

        Args:
            key (str): The unique key identifying the shortened URL.
            custom_domain (str): The custom domain associated with the shortened URL.

        Returns:
            Type[TrackShortenUrlResponseDTO]: Tracking data for the shortened URL.
        """
        track_shorten_url_body = TrackShortenUrlBodyDTO(
            key=key, customDomain=custom_domain
        )
        response: Response = self._make_request(
            method=HTTPMethod.POST,
            endpoint='track',
            body=track_shorten_url_body.to_dict(),
        )
        return self.validate_response_data(
            response=response, base_model_class=TrackShortenUrlResponseDTO
        )
