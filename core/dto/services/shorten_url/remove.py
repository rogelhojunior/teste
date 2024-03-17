from typing import Optional, Union

from pydantic import AnyUrl, BaseModel, HttpUrl, field_validator


class RemoveShortenUrlBodyDTO(BaseModel):
    key: str
    customDomain: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        return self.model_dump(by_alias=True, exclude_none=True)


class RemoveShortenUrlMetadata(BaseModel):
    longUrl: Union[HttpUrl, AnyUrl]
    domain: str
    key: str

    @field_validator('longUrl', mode='after')
    def format_long_url(cls, long_url: Union[HttpUrl, AnyUrl]) -> str:
        return str(long_url)


class RemoveURLResponseDTO(BaseModel):
    message: str
    metadata: RemoveShortenUrlMetadata
