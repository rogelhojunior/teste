from contract.models.contratos import Contrato
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.validacao_contrato import ValidacaoContrato
from custom_auth.models import Corban
from documentscopy.choices import CorbanTableOptions
from documentscopy.models import UnicoParameter, UnicoParameterFaceMatch


class ScoreValidation:
    def __init__(
        self,
        contract: Contrato,
        envelope: EnvelopeContratos,
        status: int,
        score: float,
        product: object,
    ):
        self.contract = contract
        self.envelope = envelope
        self.status = status
        self.score = score
        self.parameter = None
        self.score_rules = None
        self.product = product
        self.error = False
        self.restrictive_error = False

    def get_unico_parameter(self):
        if UnicoParameter.objects.filter(
            products=self.contract.tipo_produto, stores=self.contract.corban
        ).exists():
            self.parameter = UnicoParameter.objects.get(
                products=self.contract.tipo_produto, stores=self.contract.corban
            )
            return True
        else:
            corban_master = Corban.objects.get(
                corban_CNPJ=self.contract.corban.corban_CNPJ
            ).parent_corban
            if UnicoParameter.objects.filter(
                products=self.contract.tipo_produto, corbans=corban_master
            ).exists():
                if not UnicoParameter.objects.get(
                    products=self.contract.tipo_produto, corbans=corban_master
                ).stores.exists():
                    self.parameter = UnicoParameter.objects.get(
                        products=self.contract.tipo_produto, corbans=corban_master
                    )
                    return True

    def get_unico_parameter_facematch(self):
        if UnicoParameterFaceMatch.objects.filter(parameter=self.parameter).exists():
            self.score_rules = UnicoParameterFaceMatch.objects.filter(
                parameter=self.parameter
            )
            return True
        return False

    def set_validation_contracts(self, checked: bool, hub_return: str):
        validado, _ = ValidacaoContrato.objects.update_or_create(
            contrato=self.contract,
            mensagem_observacao='Regra Score UNICO',
            defaults={
                'mensagem_observacao': 'Regra Score UNICO',
                'checked': checked,
            },
        )
        validado.retorno_hub = hub_return
        validado.save()
        self.envelope.erro_unico = self.error
        self.envelope.erro_restritivo_unico = self.restrictive_error
        self.envelope.save()

    def set_corban_action_status(self, corban_action):
        if corban_action == CorbanTableOptions.APPROVE:
            self.error = False
            self.restrictive_error = False
            self.set_validation_contracts(True, f'SCORE APROVADO Valor: {self.score}')
        elif corban_action == CorbanTableOptions.PENDING:
            self.error = True
            self.restrictive_error = False
            self.set_validation_contracts(
                False, f'SCORE PENDENCIADO Valor: {self.score}'
            )
        elif corban_action == CorbanTableOptions.DISAPPROVE:
            self.error = False
            self.restrictive_error = True
            self.set_validation_contracts(False, f'SCORE REPROVADO Valor: {self.score}')

    def execute(self):
        self.get_unico_parameter()
        if self.parameter:
            self.get_unico_parameter_facematch()
            if self.score_rules:
                for rule in self.score_rules:
                    if rule.score_from < self.score < rule.score_to:
                        self.set_corban_action_status(rule.corban_action)
                        return (
                            True,
                            self.error,
                            self.restrictive_error,
                        )
        return False, False, False
