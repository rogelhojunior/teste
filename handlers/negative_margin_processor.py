import decimal

from django.conf import settings
from django.db import models
from rest_framework.exceptions import ValidationError

from contract.models.contratos import Contrato, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from custom_auth.models import UserProfile


class NegativeMarginProcessor:
    """
    Processes in100 data, and apply negative margin rules
    """

    DENY_STATUS = ContractStatus.REPROVADO.value

    def __init__(
        self,
        in100: DadosIn100,
        product_type: int,
    ):
        """
        Initialize all needed attributes

        Args:
            in100: In100 data to be evaluated
            product_type: Contract product type (e.g.) Portability, Free Margin, Benefit Card...

        """
        self.in100 = in100
        self.product_type = product_type
        self.user = self.get_qi_tech_user()

    def get_new_installment(self, portability: Portabilidade):
        """
        Gets new installment.
        Args:
            portability: Portability instance.
        Returns: Recalculated installment or first new typed installment.
        """
        return portability.valor_parcela_recalculada or portability.nova_parcela

    def get_original_installment(self, portability: Portabilidade):
        """
        Gets original installment.
        Args:
            portability: Portability instance.
        Returns: Original installment or first typed installment.
        """
        return portability.valor_parcela_original or portability.parcela_digitada

    def validate_negative_margin(self):
        """
        Validates if in100 data is with NegativeMargin
        Raises:
            ValidationError: if in100 data has margin value not negative.
        """
        if self.in100.valor_margem >= 0:
            raise ValidationError({
                'Erro': 'O valor da margem in100 precisa ser negativo.'
                ' Esta classe é apenas para Margem Negativa.',
            })

    def get_qi_tech_user(self) -> UserProfile:
        """
        Returns: QI Tech user
        """
        return UserProfile.objects.get(
            identifier=settings.QITECH_USER,
        )

    def update_contract_instance_status(
        self,
        contract: Contrato,
        status: int,
    ):
        """
        Updates contract instance status
        Args:
            contract: Contract Instance to be updated
            status: Enum status from ContractStatus
        """
        contract.status = status
        contract.save()

    def update_portability_status(
        self,
        portability: Portabilidade,
        status: int,
    ):
        """
        Updates contract instance status
        Args:
            portability: Portability Instance to be updated
            status: Enum status from ContractStatus
        """
        portability.status = status
        portability.save()

    def create_contract_status(
        self,
        contract: Contrato,
        status: int,
        mesa_description: str = None,
    ):
        """
        Creates StatusContrato instance.
        Args:
            user: User responsible for this status update
            contract: Contract Instance to be updated
            status: Enum status from ContractStatus
            mesa_description: (optional) Description about the defined status
        """
        StatusContrato.objects.create(
            contrato=contract,
            nome=status,
            created_by=self.user,
            descricao_mesa=mesa_description,
        )

    def get_last_status_subquery(self) -> models.Subquery:
        """
        Return subquery for last status defined in StatusContrato model.
        Returns: Subquery object, with contrato_id reference
        """
        return models.Subquery(
            StatusContrato.objects.filter(contrato_id=models.OuterRef('pk'))
            .order_by('-data_fase_inicial')
            .values('nome')[:1],
            output_field=models.CharField(),
        )

    def get_contracts(self) -> models.QuerySet[Contrato]:
        """
        Get all contracts from in100 client and product defined.
        Annotates last status as database column, and filter by specified status.
        Returns: Contrato Queryset
        """

        return Contrato.objects.annotate(
            ultimo_status=self.get_last_status_subquery()
        ).filter(
            cliente=self.in100.cliente,
            tipo_produto=self.product_type,
            ultimo_status__in=[
                ContractStatus.AGUARDA_ENVIO_LINK.value,
                ContractStatus.FORMALIZACAO_CLIENTE.value,
                ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                ContractStatus.AGUARDANDO_IN100_RECALCULO.value,
            ],
        )

    def is_new_installment_valid(self, portability: Portabilidade) -> bool:
        """
        Verifies new installment is still valid, with negative margin returns.
        The basic rule is that the new installment
         always need to be lower than typed value and typed value + negative margin
        Args:
            portability: Portability instance

        Returns:
            bool: True if new installment is still valid, False otherwise.
        Examples:
        (1)
            typed_installment = 250
            negative_margin = -5
            new_installment = 230
            250 + (-5) > 230 -> True
        (2)
            typed_installment = 240
            negative_margin = -10
            new_installment = 230
            240 + (-10) > 230 -> True
        (3)
            typed_installment = 240
            negative_margin = -15
            new_installment = 230
            240 + (-15) > 230 -> False
        """
        new_installment = self.get_new_installment(portability)
        original_installment = self.get_original_installment(portability)
        return new_installment <= (
            decimal.Decimal(original_installment)
            + decimal.Decimal(self.in100.valor_margem)
        )

    def deny_contract(
        self,
        contract: Contrato,
        mesa_description: str,
    ):
        """
        Denies contract
        Args:
            contract: Contrato instance to be denied
            mesa_description: Denial reason description
        """
        self.update_contract_instance_status(
            contract,
            self.DENY_STATUS,
        )
        self.update_portability_status(
            contract.contrato_portabilidade.first(),
            self.DENY_STATUS,
        )
        self.create_contract_status(
            contract,
            self.DENY_STATUS,
            mesa_description,
        )

    def deny_all_envelope_contracts(
        self, envelope_contracts: models.QuerySet[Contrato]
    ):
        """
        Deny all contracts from specified envelope token.
        Args:
            envelope_contracts: Contract from envelope
        """
        contracts = envelope_contracts.annotate(
            ultimo_status=self.get_last_status_subquery(),
        ).exclude(
            ultimo_status__in=[
                ContractStatus.INT_FINALIZADO.value,
                ContractStatus.INT_AGUARDA_AVERBACAO.value,
                ContractStatus.INT_AVERBACAO_PENDENTE.value,
                ContractStatus.REPROVADO.value,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
                ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
                ContractStatus.REPROVADA_MESA_CORBAN.value,
            ]
        )
        for contract in contracts:
            self.deny_contract(
                contract,
                'Só é permitido um contrato com margem negativa.' ' Refaça a operação.',
            )

    def execute(
        self,
    ):
        """
        Checks if the margin is negative and, if so, applies the necessary checks.
        If there is only one contract, it checks the entered installment amount.
        If there are multiple contracts with this status, rejects all of them.

        """
        self.validate_negative_margin()

        if contracts := self.get_contracts():
            nr_contracts = contracts.count()
            if nr_contracts == 1:
                contract = contracts.first()

                envelope_contracts = Contrato.objects.filter(
                    token_envelope=contract.token_envelope,
                )

                if envelope_contracts.count() > 1:
                    self.deny_all_envelope_contracts(envelope_contracts)

                elif not self.is_new_installment_valid(
                    contract.contrato_portabilidade.first()
                ):
                    self.deny_contract(
                        contract,
                        'Não passou nas validações de margem negativa.'
                        ' O valor da nova parcela é maior que a margem negativa + a parcela digitada.',
                    )
            elif nr_contracts > 1:
                for contract in contracts:
                    self.deny_contract(
                        contract,
                        'Só é permitido um contrato com margem negativa.'
                        ' Refaça a operação.',
                    )

        # TODO Verify when there's no contracts in this stage
