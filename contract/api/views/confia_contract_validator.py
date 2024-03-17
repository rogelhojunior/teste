"""This module implements the class ConfiaContractValidator."""

# thirds

# local

from .unico_score_contract_validator import UnicoScoreContractValidator

# constants
CONFIA_RULE_DESCRIPTION = 'Regra Score CONFIA'


class ConfiaContractValidator(UnicoScoreContractValidator):
    """
    Confia score validator to a contract.

    Attributes:
        contract (Contrato): a reference to the contract
            being updated.
        sub_contract (Portabilidade | CartaoBeneficio |
            SaqueComplementar): a contract have a "tipo_produto"
            attribute, this key inform that there is a record of a
            specific type pointing to this contract, we are naming this
            record as "sub contract" to improve readability. The sub
            contract record must have the status updated too.
    """

    @property
    def validation_message(self) -> str:
        return CONFIA_RULE_DESCRIPTION

    @property
    def is_score_approved(self) -> bool:
        """Does the score means approved ?"""
        return self.score is True

    @property
    def is_score_disapproved(self) -> bool:
        """Does the score means disapproved ?"""
        return self.score is False

    def validate(self) -> None:
        """Update contract data."""
        if self.is_success_status():
            if self.is_score_approved:
                self.approve_contract()

            elif self.is_score_disapproved:
                self.disapprove_contract(f'SCORE REPROVADO Valor: {self.score}')

        elif self.is_divergency_status():
            self.disapprove_contract('SCORE REPROVADO Divergencia na CONFIA')
