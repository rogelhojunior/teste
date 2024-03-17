import logging

from rest_framework.exceptions import ValidationError

from contract.constants import EnumTipoProduto
from contract.services.validators.in100 import is_contract_end_date_valid
from core.models.cliente import Cliente
from core.models.parametro_produto import ParametrosProduto
from core.utils import calcular_idade
from handlers.validar_regras_beneficio_contrato import (
    ValidadorRegrasBeneficioCliente,
    valida_faixa_idade,
)


class PortRefinSimulationValidation:
    def __init__(self, cpf: str) -> None:
        """
        Initializes an instance of the class.

        Parameters:
            cpf (str): The CPF of the customer.

        Returns:
            None
        """

        self.customer = Cliente.objects.filter(nu_cpf=cpf).last()

        if not self.customer:
            raise ValidationError({'Erro': 'Cliente não encontrado.'})

        self.customer_age = calcular_idade(self.customer.dt_nascimento)
        self.in100_data = self.customer.get_first_in100()
        self.eligibility_rules = ParametrosProduto.objects.filter(
            tipoProduto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
        ).first()

        self.logger = logging.getLogger('digitacao')

    def pre_simulation(
        self,
        refin_installment_amount: float,
        original_installment_amount: float,
        refin_installments_quantity: int,
        due_amount: float,
    ) -> bool:
        """
        Check if the simulation is valid based on the given parameters before making the request.

        Args:
            refin_installment_amount (float): The refinanced installment amount.
            original_installment_amount (float): The original installment amount.
            refin_installments_quantity (int): The quantity of refinanced installments.

        Returns:
            bool: True if the pre-simulation is valid, False otherwise.
        """

        if not self.eligibility_rules:
            raise ValidationError({'Erro': 'Regras não cadastradas para o produto.'})

        if refin_installment_amount > original_installment_amount:
            raise ValidationError({'Erro': 'Valor superior ao permitido.'})

        # validate PORT+REFIN contract minimum value
        min_value = self.eligibility_rules.valor_minimo_emprestimo
        if due_amount < min_value:
            msg = 'Valor minimo para esse tipo de contrato é %0.2f' % min_value
            raise ValidationError({'Erro': msg})

        if self.in100_data and self.in100_data.retornou_IN100:
            benefit_customer_validator = ValidadorRegrasBeneficioCliente(
                cliente=self.customer, dados_in100=self.in100_data
            )
            benefit_customer_validator.set_parcelas(
                parcelas=refin_installments_quantity
            )

            if not benefit_customer_validator.validar_regra_morte().get(
                'regra_aprovada'
            ):
                raise ValidationError({'Erro': 'Fora da política.'})

        if (
            self.in100_data
            and self.in100_data.retornou_IN100
            and not is_contract_end_date_valid(
                self.in100_data.data_expiracao_beneficio,
                refin_installments_quantity,
            )
        ):
            raise ValidationError({
                'Erro': 'Prazo do empréstimo maior que o prazo do benefício'
            })

        return True

    def post_simulation(
        self,
        refin_change: float,
        refin_installments_quantity: int,
        refin_total_amount: float,
        portability_monthly_interest_rate: float,
    ) -> str:
        """
        Check if the simulation is valid based on the given parameters after making the request.

        Args:
            refin_change (float): The amount of change.
            refin_installments_quantity (int): The number of installments.
            refin_total_amount (float): The total amount.
            portability_monthly_interest_rate (float): The portability monthly interest rate.

        Returns:
            str: An error message indicating any validation issues encountered.
        """

        error_msg = ''

        if not valida_faixa_idade(
            cliente=self.customer,
            parcelas=refin_installments_quantity,
            valor_cliente=refin_total_amount,
        ):
            error_msg = 'Fora da política.'

        elif refin_change < 0:
            error_msg = 'Valor do troco negativo.'

        elif refin_change < float(self.eligibility_rules.valor_troco_minimo):
            error_msg = 'Valor do troco inferior ao mínimo permitido.'

        elif refin_total_amount >= float(
            self.eligibility_rules.valor_liberado_cliente_operacao_max
        ):
            error_msg = 'Valor da operação maior que o maximo permitido.'

        elif (
            self.eligibility_rules.teto_inss
            and portability_monthly_interest_rate
            > float(self.eligibility_rules.teto_inss)
        ):
            error_msg = 'Contrato da Port com taxa acima do teto do INSS.'

        return error_msg
