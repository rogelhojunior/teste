from datetime import date, time
from typing import Optional, Union

from pydantic import AnyUrl, BaseModel, HttpUrl, field_validator


class TrackShortenUrlBodyDTO(BaseModel):
    key: str
    customDomain: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        return self.model_dump(by_alias=True, exclude_none=True)


class PlatformInfo(BaseModel):
    name: str
    version: str


class OSInfo(BaseModel):
    name: str


class FlavourInfo(BaseModel):
    name: str
    version: str


class BrowserInfo(BaseModel):
    name: str
    version: str


class UserInfo(BaseModel):
    platform: PlatformInfo
    os: OSInfo
    bot: bool
    flavour: Optional[FlavourInfo]
    browser: BrowserInfo


class HitInfo(BaseModel):
    date: date
    time: time
    ip: str
    method: str
    resource: str
    referrer: str
    user: UserInfo
    rawUserAgent: str
    timeTaken: float


class TrackShortenUrlMetadata(BaseModel):
    longUrl: Union[HttpUrl, AnyUrl]
    domain: str
    key: str

    @field_validator('longUrl', mode='after')
    def format_long_url(cls, long_url: Union[HttpUrl, AnyUrl]) -> str:
        return str(long_url)


class TrackShortenUrlResponseDTO(BaseModel):
    totalHits: int
    hits: list[HitInfo]
    metadata: TrackShortenUrlMetadata
