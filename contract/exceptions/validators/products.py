from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from core.common.exceptions import ClientException, MensagemErro


class ClientCPFContractLimitExceeded(ClientException):
    def __init__(self, valid_existing_contracts_amount: int):
        self.message: MensagemErro = MensagemErro(
            Erro=_(
                'Não foi possível criar o contrato. '
                'Limite de contratos ativos atingido, '
                f'{valid_existing_contracts_amount} contrato(s) '
                'ativos para este cliente atualmente.'
            )
        )
        super().__init__(message=self.message)


class RogadoException(ValidationError):
    default_message = _('Houve um erro ao criar o Rogado, verifique os dados enviados.')

    def __init__(self, description: str):
        super().__init__({
            'Erro': self.default_message,
            'description': description,
        })


class WitnessException(ValidationError):
    default_message = _(
        'Houve um erro ao criar as Testemunhas, verifique os dados enviados.'
    )

    def __init__(self, description: str):
        super().__init__({
            'Erro': self.default_message,
            'description': description,
        })
