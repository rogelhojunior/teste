from django.utils.translation import gettext as _

from core.common.exceptions import ClientException, ErrorMessage


class InsufficientFreeMarginForContract(ClientException):
    def __init__(self):
        # TODO: Translate this message into English
        self.message: ErrorMessage = ErrorMessage(
            error=_('Você não possui margem disponível para realizar um novo contrato.')
        )
        super().__init__(message=self.message)


class CPFLengthException(ClientException):
    def __init__(self):
        self.message: ErrorMessage = ErrorMessage(
            error=_('CPF deve conter 11 dígitos.')
        )
        super().__init__(message=self.message)


class InvalidCPFException(ClientException):
    def __init__(self):
        self.message: ErrorMessage = ErrorMessage(error=_('CPF inválido.'))
        super().__init__(message=self.message)
