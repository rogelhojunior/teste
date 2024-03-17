from django.utils.translation import gettext as _

from core.common.exceptions import ClientException


class SimulateFreeMarginContractException(ClientException):
    def __init__(self):
        self.message: str = _(
            'Não foi possível realizar a simulação. Fora da política.'
        )
        super().__init__(message=self.message)
