from typing import NoReturn, Optional

from contract.models.contratos import Contrato, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.models import Cliente
from custom_auth.models import UserProfile
from handlers.qitech_api.adapters.portability_proposal import (
    PortabilityProposalEndpointParams,
)
from handlers.qitech_api.dto.portability_proposal.response import PortabilityProposalDTO
from handlers.qitech_api.exceptions.portability_proposal import (
    IncorrectPortabilityDataException,
)
from handlers.qitech_api.services.qitech_api import QiTechApiService
import logging

logger = logging.getLogger('webhookqitech')


# TODO: Remove this validator from qitech_api package
class PortabilityProposalValidator:
    """
    A validator class for portability proposals.

    This class is responsible for validating the data of a portability proposal
    to ensure its correctness and integrity.

    Attributes:
        portability (Portabilidade): An instance of Portabilidade containing proposal data.
        proposal_key (str): Key of the portability proposal.
        contract (Contrato): Contract associated with the portability.
        client (Cliente): Client associated with the contract.
        in100 (DadosIn100): IN100 data of the client.
        cpf (str): CPF number of the client.
        benefit_number (str): Benefit number from the IN100 data.
        portability_proposal (PortabilityProposalDTO): The portability proposal DTO.

    Methods:
        get_proposal: Retrieves the portability proposal using the proposal key.
        get_validate_data: Extracts and returns data for validation.
        validate_proposal_data: Validates the proposal data.
        check_portability_proposal: Checks the validity of the portability proposal.
    """

    def __init__(self, portability: Portabilidade) -> None:
        """
        Initializes the PortabilityProposalValidator with a portability instance.

        Args:
            portability (Portabilidade): An instance of Portabilidade Model.
        """
        self.portability: Portabilidade = portability
        self.proposal_key: str = self.portability.chave_proposta

        self.contract: Contrato = self.portability.contrato
        self.client: Cliente = self.contract.cliente
        self.in100: DadosIn100 = DadosIn100.objects.filter(
            numero_beneficio=self.contract.numero_beneficio, cliente=self.client
        ).first()

        self.cpf: str = self.client.nu_cpf_
        self.benefit_number: str = self.in100.numero_beneficio

        self.portability_proposal: PortabilityProposalDTO = self.get_proposal()

    def get_proposal(self) -> PortabilityProposalDTO:
        """
        Retrieves the portability proposal using the proposal key.

        Returns:
            PortabilityProposalDTO: The retrieved loaded portability proposal DTO.
        """
        endpoint_params = PortabilityProposalEndpointParams(
            proposal_key=self.proposal_key
        )
        return QiTechApiService.execute(
            adapter_name='portability_proposal', endpoint_params=endpoint_params
        )

    def get_validate_data(self) -> tuple[dict[str, any], dict[str, any]]:
        """
        Extracts and returns data from the portability proposal and associated objects
        for validation purposes.

        Returns:
            tuple[dict[str, any], dict[str, any]]: A tuple containing two dictionaries -
            one with the contract data and another with the proposal data for validation.
        """
        benefit_number = self.portability_proposal.collaterals[
            0
        ].collateral_data.benefit_number
        contract_number = (
            self.portability_proposal.portability_credit_operation.contract_number
        )
        portability_contract_data = {
            'cpf': self.portability_proposal.borrower.individual_document_number,
            'benefit_number': str(benefit_number),
            'contract_number': contract_number,
            'origin_operation_contract_number': self.portability_proposal.origin_operation.contract_number,
        }
        portability_proposal_data = {
            'cpf': self.cpf,
            'benefit_number': str(self.benefit_number),
            'contract_number': self.contract.id,
            'origin_operation_contract_number': self.portability.numero_contrato,
        }
        return portability_contract_data, portability_proposal_data

    def validate_proposal_data(self) -> bool:
        """
        Validates the proposal data by comparing the extracted data from the portability
        proposal and the associated objects.

        Returns:
            bool: True if the validation is successful, False otherwise.
        """
        portability_contract_data, portability_proposal_data = self.get_validate_data()
        return portability_contract_data == portability_proposal_data

    def check_portability_proposal(self) -> Optional[NoReturn]:
        """
        Checks the validity of the portability proposal. Raises an exception if the
        validation fails.

        Returns:
            Optional[NoReturn]: None if validation is successful.

        Raises:
            IncorrectPortabilityDataException: If the proposal data is not valid.
        """
        if not self.validate_proposal_data():
            raise IncorrectPortabilityDataException

    def execute(self, user: UserProfile):
        """
        Executes the validation process for the portability proposal.

        This method triggers the validation of the portability proposal data. If the
        validation fails, it updates the status of the portability to rejected and logs
        the status change along with the reason for rejection.

        Args:
            user (UserProfile): The user profile performing the validation.

        Raises:
            IncorrectPortabilityDataException: If the portability proposal data fails validation.
                This exception is caught within the method, and the status of the portability
                is updated accordingly before re-raising the exception.
        """
        try:
            PortabilityProposalValidator(
                portability=self.portability
            ).check_portability_proposal()
        except IncorrectPortabilityDataException as error:
            self.portability.status = ContractStatus.REPROVADO.value
            self.portability.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=self.contract,
                nome=ContractStatus.REPROVADO.value,
                created_by=user,
                descricao_mesa=error.message.get('error', ''),
            )
            message = (
                f'{self.client.id_unico} - Contrato(ID: {self.contract.pk}):'
                f"Saldo Reprovado por 'Dados de portabilidade incorretos'"
            )
            logger.info(message)
            raise
