from django.utils.translation import gettext as _

from core.common.exceptions import ClientException, ErrorMessage


class IncorrectPortabilityDataException(ClientException):
    def __init__(self):
        self.message: ErrorMessage = ErrorMessage(
            error=_('Dados de portabilidade incorretos')
        )
        super().__init__(message=self.message)
