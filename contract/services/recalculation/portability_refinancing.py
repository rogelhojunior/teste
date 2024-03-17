import logging

from requests import HTTPError
from rest_framework.exceptions import ValidationError

from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.models.taxa import Taxa
from contract.products.portabilidade_refin.calcs import calc_refin_change
from contract.products.portabilidade_refin.handlers import (
    CancelRefinancing,
    PutRefinancingOnHold,
)
from core.constants import EnumAcaoCorban
from core.models.parametro_produto import ParametrosProduto
from handlers.qitech import QiTech
from handlers.validar_regras_beneficio_contrato import (
    ValidadorRegrasBeneficioContratoPortabilidadeRefinanciamento,
)


class RefinancingRecalculation:
    FIRST_INCREMENT_FACTOR = 0.1
    SECOND_INCREMENT_FACTOR = 0.01

    def __init__(
        self,
        contract: Contrato,
        portability: Portabilidade,
    ):
        self.contract = contract
        self.client = self.contract.cliente
        self.portability = portability
        self.refinancing = Refinanciamento.objects.get(contrato=self.contract)
        self.product_params = ParametrosProduto.objects.get(
            tipoProduto=contract.tipo_produto
        )
        self.in100 = DadosIn100.objects.filter(
            numero_beneficio=self.contract.numero_beneficio
        ).first()

    @staticmethod
    def get_refused_status() -> list:
        return [
            ContractStatus.REPROVADO.value,
            ContractStatus.REPROVADA_POLITICA_INTERNA.value,
            ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
            ContractStatus.REPROVADA_FINALIZADA.value,
            ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
        ]

    def get_corban_status(self) -> int:
        if (
            self.refinancing.valor_total_recalculado
            < self.product_params.valor_minimo_emprestimo
        ):
            return EnumAcaoCorban.RECUSAR

        original_refin_change = float(self.refinancing.troco)
        new_refin_change = float(self.refinancing.troco_recalculado)

        if new_refin_change < float(self.product_params.valor_troco_minimo):
            return EnumAcaoCorban.RECUSAR

        if new_refin_change >= original_refin_change:
            return EnumAcaoCorban.APROVAR

        reduction_percentage = (
            (original_refin_change - new_refin_change) / original_refin_change
        ) * 100

        if reduction_percentage <= float(
            self.product_params.percentual_maximo_aprovacao
        ):
            return EnumAcaoCorban.APROVAR
        elif reduction_percentage <= float(
            self.product_params.percentual_maximo_pendencia
        ):
            return EnumAcaoCorban.PENDENCIAR

        return EnumAcaoCorban.RECUSAR

    def get_simulation_default_params(self) -> dict:
        return {
            'original_installment_amount': float(
                self.portability.valor_parcela_original
            ),
            'due_installments_quantity': self.portability.numero_parcela_atualizada,
            'refin_installment_amount': float(self.portability.valor_parcela_original),
            'refin_installments_quantity': self.refinancing.prazo,
            'due_amount': float(self.portability.saldo_devedor_atualizado),
        }

    def get_reframe_operation_payload(self) -> dict:
        return {
            **self.get_simulation_default_params(),
            'disbursed_amount': float(self.portability.saldo_devedor_atualizado)
            - float(self.product_params.valor_troco_minimo),
        }

    def get_simulation_payload(self, monthly_interest: float) -> dict:
        return {
            **self.get_simulation_default_params(),
            'monthly_interest': float(monthly_interest) / 100,
        }

    def get_qitech_response(
        self,
        function: callable,
        params: dict,
    ) -> dict:
        decoded_response = {}
        try:
            qi_tech = QiTech()
            response = function(
                **params,
            )
            decoded_response = qi_tech.decode_body(response_json=response.json())
            response.raise_for_status()
            return decoded_response
        except HTTPError as e:
            logger = logging.getLogger('webhookqitech')
            logger.critical(
                'Erro ao simular a proposta de refinanciamento com o retorno do saldo na QI Tech',
                extra={'extra': decoded_response},
            )
            raise ValidationError(
                {'Erro': 'Ocorreu um erro ao simular o refinanciamento na QI Tech'},
            ) from e

    def validate_refin_data(self, refin_data_list: list):
        if not refin_data_list:
            raise ValidationError(
                {'Erro': 'Ocorreu um erro ao simular o refinanciamento na QI Tech'},
            )

    def update_refinancing(
        self, disbursement_options: list, monthly_interest_rate: float
    ):
        refin_data = disbursement_options[0]

        refin_total_amount = refin_data.get('disbursed_issue_amount')

        self.refinancing.valor_total_recalculado = refin_data.get(
            'disbursed_issue_amount'
        )
        self.refinancing.troco_recalculado = calc_refin_change(
            due_amount=float(self.portability.saldo_devedor_atualizado),
            refin_total_amount=refin_total_amount,
        )

        self.refinancing.taxa_contrato_recalculada = monthly_interest_rate

    def verify_refin_change(self) -> bool:
        """
        Verifies if refinancing change is greater than the minimum change allowed.
        Returns:
            bool - True if refinancing change is greater than the minimum allowed.
        """
        if (
            refin_percentage_change
            := self.product_params.percentual_variacao_troco_recalculo
        ) and float(self.refinancing.troco_recalculado) < float(self.refinancing.troco):
            return float(self.refinancing.troco_recalculado) > float(
                self.refinancing.troco
            ) * (1 - float(refin_percentage_change) / 100)
        return True

    def process_decoded_response(self, decoded_response: dict, interest_rate: float):
        self.update_refinancing(
            disbursement_options=self.extract_disbursement_options(decoded_response),
            monthly_interest_rate=interest_rate,
        )

    def validate_age_range_rules(self) -> bool:
        """
        Validates age range rules.
        Returns:
            bool - True if contract is valid, otherwise False.

        """
        return (
            ValidadorRegrasBeneficioContratoPortabilidadeRefinanciamento(
                contrato=self.contract,
                dados_in100=self.in100,
                refinancing=self.refinancing,
            )
            .validar_regra_faixa_idade()
            .get('regra_aprovada', False)
        )

    def execute(self):
        if self.portability.status not in self.get_refused_status():
            # Realiza o recálculo da operação e depois
            self.recalculate_operation()

            self.refinancing.save(
                update_fields=[
                    'valor_total_recalculado',
                    'troco_recalculado',
                    'taxa_contrato_recalculada',
                ]
            )
        else:
            self.cancel_operation(
                reason='Refinanciamento cancelado pois o recálculo da Portabilidade foi reprovado.'
            )

    def extract_disbursement_options(self, decoded_response: dict) -> list:
        return decoded_response.get('refinancing_credit_operation', {}).get(
            'disbursement_options',
            [],
        )

    def get_available_product_fees(self) -> list[float]:
        """
        Returns ordered available fees, based on current product fee.
        Args:
            current_fee: Current product free
        Returns:
            list: Descending ordered list with available fees.
        """
        return [
            round(float(fee), 4)
            for fee in Taxa.objects.filter(
                ativo=True,
                tipo_produto=self.contract.tipo_produto,
                taxa__lte=self.refinancing.taxa,
            )
            .values_list('taxa', flat=True)
            .order_by('-taxa')
        ]

    def pend_operation(
        self,
        reason='Aguardando aprovação do valor do troco recalculado',
    ):
        return PutRefinancingOnHold(
            refinancing=self.refinancing,
            portability=self.portability,
            reason=reason,
        ).execute()

    def approve_operation(self):
        from handlers.webhook_qitech import validar_in100_recalculo

        return validar_in100_recalculo(self.contract)

    def cancel_operation(self, reason):
        return CancelRefinancing(
            refinancing=self.refinancing,
            reason=reason,
        ).execute()

    def recalculate_operation(
        self,
    ):
        """
        Recalculates refinancing.

        When monthly interest rate is greater than minimum fee,
        is necessary to verify if refinancing change is greater than the minimum change allowed.

        Only cancel refinancing in lower interest rate if refinancing change.

        """
        qi_tech = QiTech()
        for monthly_interest_rate in self.get_available_product_fees():
            decoded_response = self.get_qitech_response(
                function=qi_tech.simulation_port_refin,
                params=self.get_simulation_payload(monthly_interest_rate),
            )
            self.process_decoded_response(
                decoded_response,
                monthly_interest_rate,
            )

            is_age_rules_valid = self.validate_age_range_rules()
            if monthly_interest_rate > float(self.product_params.taxa_minima):
                if is_age_rules_valid and self.verify_refin_change():
                    status_corban = self.get_corban_status()
                    if status_corban == EnumAcaoCorban.PENDENCIAR:
                        return self.pend_operation()
                    elif status_corban == EnumAcaoCorban.APROVAR:
                        return self.approve_operation()
            else:
                if is_age_rules_valid and (status_corban := self.get_corban_status()):
                    if status_corban == EnumAcaoCorban.PENDENCIAR:
                        return self.pend_operation()
                    elif status_corban == EnumAcaoCorban.APROVAR:
                        return self.approve_operation()
                    elif status_corban == EnumAcaoCorban.RECUSAR:
                        return self.cancel_operation(
                            reason='Valor do troco (recálculo) fora da politica'
                        )
                return self.cancel_operation(
                    reason='Recálculo não passou na regra de faixa de idade'
                )
