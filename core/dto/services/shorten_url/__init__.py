from typing import TypeVar

from pydantic import BaseModel

ResponseModelType = TypeVar('ResponseModelType', bound=BaseModel)
