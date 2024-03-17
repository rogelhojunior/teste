from http import HTTPStatus
from typing import Optional, TypedDict, Union

from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST


class ErrorMessage(TypedDict):
    """TypedDict to defining error message format"""

    error: str


# TODO: Formato antigo de mensagem de erro, mudar para a nova ErrorMessage
class MensagemErro(TypedDict):
    """TypedDict to defining error message format"""

    Erro: str


class ClientException(ValidationError):
    """Base class for client exceptions"""

    status_code: Optional[HTTPStatus] = HTTP_400_BAD_REQUEST

    def __init__(self, message: Union[ErrorMessage, MensagemErro, str]):
        self.message: Union[ErrorMessage, MensagemErro, str] = message
        super().__init__(detail=self.message, code=self.status_code)
