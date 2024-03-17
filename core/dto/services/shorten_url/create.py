from datetime import datetime
from typing import Optional, Union

from pydantic import AnyUrl, BaseModel, HttpUrl, field_validator


class ShortenUrlMetadata(BaseModel):
    domain: str
    longUrl: Union[HttpUrl, AnyUrl]
    key: str
    expiration: datetime

    @field_validator('longUrl', mode='after')
    def format_long_url(cls, long_url: Union[HttpUrl, AnyUrl]) -> str:
        return str(long_url)


class ShortenUrlResponseDTO(BaseModel):
    shortUrl: HttpUrl
    metadata: ShortenUrlMetadata

    @field_validator('shortUrl', mode='before')
    def format_short_url(cls, short_url: str) -> str:
        if not short_url.startswith('http://') and not short_url.startswith('https://'):
            return f'https://{short_url}'
        return short_url


class ShortenUrlBodyDTO(BaseModel):
    longUrl: Union[HttpUrl, AnyUrl]
    customKey: Optional[str] = None
    expireHours: Optional[int] = None
    keyLength: Optional[int] = None
    customDomain: Optional[str] = None

    @field_validator('longUrl', mode='after')
    def format_long_url(cls, long_url: Union[HttpUrl, AnyUrl]) -> str:
        return str(long_url)

    def to_dict(self) -> dict[str, Union[str, int]]:
        return self.model_dump(by_alias=True, exclude_none=True)
