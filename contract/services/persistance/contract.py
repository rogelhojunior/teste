from typing import Optional

from django.db.models import Q

from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile
from handlers.contrato import get_contract_reproved_status


def create_contract_status(
    contract: Contrato,
    mesa_description: str,
    status: ContractStatus = ContractStatus.REPROVADO.value,
    user: Optional[UserProfile] = None,
) -> None:
    """

    Args:
        contract: Contrato instance
        mesa_description: mesa description message
        status: status to be created (default DENIED)
        user: [Optional] UserProfile object

    """
    StatusContrato.objects.create(
        contrato=contract,
        nome=status,
        descricao_mesa=mesa_description,
        created_by=user,
    )


def update_contract_status(
    contract: Contrato,
    status=EnumContratoStatus.CANCELADO,
):
    contract.status = status
    contract.save(
        update_fields=[
            'status',
        ]
    )


def get_secondary_contracts(main_contract: Contrato):
    """
    Return secondary contracts
    Args:
        main_contract: Main contract from

    Returns: Contrato queryset with only not main proposals.

    """
    return Contrato.objects.filter(
        token_envelope=main_contract.token_envelope,
        is_main_proposal=False,
    ).exclude(
        Q(id=main_contract.id)
        | Q(status=EnumContratoStatus.CANCELADO)
        | Q(contrato_portabilidade__status__in=get_contract_reproved_status())
    )


def change_main_contract_and_create_new_status(
    contract: Contrato,
    user: UserProfile,
    new_status=ContractStatus.CHECAGEM_MESA_CORBAN.value,
):
    if new_main_contract := choose_new_main_proposal(contract):
        if new_main_contract.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            product = Portabilidade.objects.get(contrato=new_main_contract)
            product.status = new_status
            product.save(update_fields=['status'])

        StatusContrato.objects.create(
            contrato=new_main_contract,
            nome=new_status,
            created_by=user,
            descricao_mesa='Novo contrato principal definido.',
        )


def choose_new_main_proposal(contract: Contrato) -> Optional[Contrato]:
    """
    Returns a Contract instance if a new main proposal was selected , otherwise returns None
    :param contract: Contract to be checked
    :return: Contrato instance
    """
    if contract.is_main_proposal:
        if new_main_contract := (
            Contrato.objects.filter(
                token_envelope=contract.token_envelope,
                is_main_proposal=False,
            )
            .exclude(
                status=EnumContratoStatus.CANCELADO,
            )
            .first()
        ):
            contract.is_main_proposal = False
            contract.save(
                update_fields=[
                    'is_main_proposal',
                ]
            )

            new_main_contract.is_main_proposal = True
            new_main_contract.save(
                update_fields=[
                    'is_main_proposal',
                ]
            )
            return new_main_contract
    return None
