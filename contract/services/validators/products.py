# TODO: Refatorar esta classe de validação para ser integrada aos Serializers,
#  garantindo que ocorra durante a validação da entrada de dados (payload).
from typing import NoReturn, Optional

from django.db.models import Q, QuerySet

from contract.constants import EnumContratoStatus, ProductTypeEnum
from contract.exceptions.validators.products import ClientCPFContractLimitExceeded
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core.models import ParametrosBackoffice
from core.settings import MAX_CONTRACT_ACTIVE_AMOUNT


class MaxContractByCPFValidator:
    """
    Validates the number of active contracts for a client based on their CPF, ensuring it does not exceed
    the maximum limit defined per product type. This validator considers both existing and proposed contracts.

    Attributes:
        max_contract_active_amount (int): Maximum allowed active contracts per client for a specific product type.
        __client_id (int): Unique identifier of the client.
        __product_type (ProductTypeEnum): Type of product associated with the contract.
        __valid_existing_contracts (QuerySet): QuerySet of the client's valid existing contracts.
        __proposals_amount (int): Number of proposed new contracts for the client.

    Args:
        client_id (int): Unique identifier of the client.
        product_type (ProductTypeEnum): Enum value representing the product type associated with the contract.
        proposals_amount (int): Number of new contract proposals for the client.

    Methods:
        __init__(self, client_id: int, product_type: ProductTypeEnum, proposals_amount: int):
            Initializes the validator with client ID, product type, and proposals amount. Sets up the
            maximum number of active contracts and retrieves the valid existing contracts.

        __get_max_contract_active_amount(self) -> int:
            Retrieves the maximum number of active contracts allowed for the specified product type.

        __get_active_contracts(self) -> QuerySet:
            Obtains a queryset of the client's active contracts, excluding those in certain excluded statuses.

        valid_existing_contracts_amount(self) -> int:
            Calculates and returns the count of the client's valid active contracts.

        validate_active_contracts(self) -> bool:
            Checks if the total number of active and proposed contracts exceeds the maximum limit.

        check_active_contracts(self) -> Optional[NoReturn]:
            Validates active contracts and raises `ClientCPFContractLimitExceeded` if the limit is exceeded.
    """

    def __init__(
        self,
        client_id: int,
        product_type: ProductTypeEnum,
        proposals_amount: int,
        numero_beneficio: str = None,
    ):
        """
        Initializes the validator with client ID, product type, and the amount of proposed contracts.
        Sets the maximum number of active contracts and retrieves valid existing contracts.

        Args:
            client_id (int): Unique identifier of the client.
            product_type (ProductTypeEnum): Enum representing the product type.
            proposals_amount (int): Number of proposed new contracts.
            numero_beneficio (int): Number of benefit.
        """
        self.__client_id: int = client_id
        self.__product_type: int = product_type.value
        self.__proposals_amount: int = proposals_amount
        self.__numero_beneficio: str = numero_beneficio

        self.max_contract_active_amount: int = self.__get_max_contract_active_amount()

        self.__valid_existing_contracts: QuerySet = self.__get_active_contracts()

    def __get_max_contract_active_amount(self) -> int:
        """
        Retrieves the maximum number of active contracts allowed for the specific product type.

        Returns:
            int: Maximum number of active contracts allowed for the product type.
        """
        return (
            ParametrosBackoffice.objects.filter(tipoProduto=self.__product_type)
            .first()
            .quantidade_contratos_por_cliente
            or MAX_CONTRACT_ACTIVE_AMOUNT
        )

    def __get_active_contracts(self) -> QuerySet:
        """
        Retrieve a queryset of the client's active contracts, excluding those in certain statuses.

        Filters out contracts in excluded statuses and returns a QuerySet of valid, active contracts.

        Returns:
            QuerySet: A queryset of the client's active contracts.
        """
        excluded_statuses: list[int] = [
            ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
            ContractStatus.REPROVADA_POLITICA_INTERNA.value,
            ContractStatus.REPROVADO.value,
            ContractStatus.SALDO_REPROVADO.value,
            ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
            ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
            ContractStatus.REPROVADA_MESA_CORBAN.value,
            ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
            ContractStatus.REPROVADA_FINALIZADA.value,
        ]
        return (
            Contrato.objects.filter(
                cliente_id=self.__client_id, numero_beneficio=self.__numero_beneficio
            )
            .exclude(status=EnumContratoStatus.CANCELADO)
            .exclude(
                Q(contrato_portabilidade__status__in=excluded_statuses)
                | Q(contrato_margem_livre__status__in=excluded_statuses)
                | Q(contrato_refinanciamento__status__in=excluded_statuses)
            )
        )

    @property
    def valid_existing_contracts_amount(self) -> int:
        """
        Calculates and returns the number of valid active contracts for the client.

        Returns:
            int: Count of the client's valid active contracts.
        """
        return self.__valid_existing_contracts.count()

    def validate_active_contracts(self) -> bool:
        """
        Determines if the total number of active and proposed contracts exceeds the maximum limit.

        Returns:
            bool: True if the total number of contracts does not exceed the limit, False otherwise.
        """
        validate_existing_contracts_amount: bool = (
            self.valid_existing_contracts_amount <= self.max_contract_active_amount
        )

        total_creating_contracts: int = (
            self.__proposals_amount + self.valid_existing_contracts_amount
        )
        validate_creating_contracts_amount: bool = (
            total_creating_contracts <= self.max_contract_active_amount
        )
        return validate_existing_contracts_amount and validate_creating_contracts_amount

    def check_active_contracts(self) -> Optional[NoReturn]:
        """
        Validates active contracts and raises an exception if the limit is exceeded.

        Raises:
            ClientCPFContractLimitExceeded: If the number of active contracts exceeds the allowed limit.
        """
        if not self.validate_active_contracts():
            raise ClientCPFContractLimitExceeded(
                valid_existing_contracts_amount=self.valid_existing_contracts_amount
            )
