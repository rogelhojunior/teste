from typing import Literal

from contract.models.contratos import Contrato
from handlers.banksoft import (
    atualizar_dados_bancarios,
    comissionamento_banksoft,
    solicitar_saque_banksoft,
)


class BanksoftAdapter:
    """
    Adapter Class for Banksoft API

    This class acts as an adapter for the Banksoft handler, encapsulating the
    complexities and functionalities of the legacy Banksoft system. The use of
    the adapter pattern here serves a dual purpose:

    1. Refactoring Layer: The adapter provides a clear and simplified interface
    to the rest of the application. This abstraction allows for easier
    maintenance and future refactoring of the legacy Banksoft code. By
    centralizing the interactions with the Banksoft system, any changes to
    the legacy system can be managed within this adapter, minimizing the
    impact on the overall application.

    2. Centralization of Code and Functionalities: The adapter centralizes the
    interaction with the Banksoft system. This reduces redundancy and
    potential inconsistencies across the application. It ensures that all
    interactions with the Banksoft system are consistent and go through a
    single point of control.
    """

    def request_withdrawal(self, client) -> Literal[400, 200]:
        return solicitar_saque_banksoft(self, client)

    def commissioning(self) -> int:
        return comissionamento_banksoft(self)

    def update_bank_details(
        self, proposal_number, account, contract: Contrato
    ) -> Literal[400, 200]:
        return atualizar_dados_bancarios(proposal_number, account, contract)
