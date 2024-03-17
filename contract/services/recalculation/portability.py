import logging
from typing import Optional

from django.conf import settings

from contract.constants import EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.products.portabilidade_refin.handlers import CancelRefinancing
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from core.models.parametro_produto import ParametrosProduto
from custom_auth.models import UserProfile
from handlers.qitech import QiTech
from handlers.simulacao_portabilidade import build_first_due_data


class PortabilityRecalculation:
    """
    Performs recalculation for portability product
    """

    def __init__(
        self,
        contract: Contrato,
        user: Optional[UserProfile] = None,
    ):
        self.contract = contract
        self.qi_tech = None
        self.portability = Portabilidade.objects.get(contrato=self.contract)

        self.original_remaining_balance = float(
            self.portability.saldo_devedor_atualizado
        )
        self.original_installment_value = float(self.portability.valor_parcela_original)
        self.typed_remaining_balance = float(self.portability.saldo_devedor)
        self.monthly_interest_rate = float(self.portability.taxa) / 100
        self.typed_installment_value = self.portability.parcela_digitada
        self.installments_number = self.portability.numero_parcela_atualizada
        self.product_params = ParametrosProduto.objects.get(
            tipoProduto=self.contract.tipo_produto
        )
        self.first_due_date = None

        self.user = user or self.get_qi_tech_user()

    def get_qi_tech_user(self) -> UserProfile:
        """
        Returns: QI Tech user
        """
        return UserProfile.objects.get(
            identifier=settings.QITECH_USER,
        )

    def update_portability_recalculation(
        self,
        recalculated_interest_rate: float,
        recalculated_installment_value: float,
    ):
        self.portability.taxa_contrato_recalculada = recalculated_interest_rate
        self.portability.valor_parcela_recalculada = recalculated_installment_value
        self.portability.save(
            update_fields=[
                'taxa_contrato_recalculada',
                'valor_parcela_recalculada',
            ]
        )

    def update_refinancing(self):
        refin = Refinanciamento.objects.get(contrato=self.contract)
        refin.nova_parcela = self.portability.valor_parcela_recalculada
        refin.save(update_fields=['nova_parcela'])

    def get_simulation_port(self):
        self.qi_tech = QiTech()
        return self.qi_tech.simulation_port_v2_fixed_released_value(
            number_of_installments=self.installments_number,
            installment_face_value=self.original_installment_value,
            due_amount=self.original_remaining_balance,
            first_due_date=self.set_first_due_date(),
        )

    def set_first_due_date(self):
        return str(build_first_due_data(EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO))

    def execute(self):
        logger = logging.getLogger('webhookqitech')
        response = self.get_simulation_port()
        decoded_response = self.qi_tech.decode_body(response_json=response.json())
        if response.status_code in (200, 201, 202):
            monthly_rate = decoded_response['portability_credit_operation'][
                'disbursement_options'
            ][0]['prefixed_interest_rate']['monthly_rate']
            monthly_rate = float(monthly_rate) * 100
            self.update_portability_recalculation(
                float(monthly_rate), float(self.original_installment_value)
            )
            self.update_refinancing()
            if self.product_params.teto_inss and float(monthly_rate) > float(
                self.product_params.teto_inss
            ):
                logger.error(
                    f'ERRO na SIMULAÇÃO: Taxa de Port Acima do TETO do INSS CONTRATO({self.contract.id})'
                    f' response: {decoded_response}'
                )
                RefuseProposalFinancialPortability(contrato=self.contract).execute()
                CancelRefinancing(
                    refinancing=Refinanciamento.objects.get(contrato=self.contract),
                    reason='Contrato da Port com taxa acima do teto do INSS',
                ).execute()

        else:
            logger.error(
                f'Houve um ERRO ao simular CONTRATO {self.contract.id} response: {decoded_response}'
            )
            if decoded_response['code'] == 'CT000009':
                RefuseProposalFinancialPortability(contrato=self.contract).execute()
                CancelRefinancing(
                    refinancing=Refinanciamento.objects.get(contrato=self.contract),
                    reason='Valor do contrato deve ser maior que o valor do desembolso',
                ).execute()
