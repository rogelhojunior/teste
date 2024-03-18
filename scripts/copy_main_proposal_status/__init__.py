"""
Esse modulo implementa um script que pode ser executado diretamente do terminal
O script contém uma lista de IDS (que deve ser editada antes de sua execução).
Cada id na lista representa um contrato, para contrato X nessa lista o script
vai buscar pelo contrato principal do envelope Y e então copiar os status de Y
para X, fazendo com que os Status do Contrato de X sejam idênticos ao de Y.

Para executar esse script simplesmente execute:

python manage.py runscript copy_main_proposal_status

"""

from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato


def run():
    ids = [
        # put here the ids you want to run
    ]

    for id in ids:
        contract = Contrato.objects.get(id=id)
        main_proposal = get_main_proposal(contract)
        if contract.id == main_proposal.id:
            continue
        clean_contract_status(contract)
        copy_status(target=main_proposal, destination=contract)


def get_main_proposal(contract):
    return Contrato.objects.get(
        token_envelope=contract.token_envelope, is_main_proposal=1
    )


def clean_contract_status(contract: Contrato):
    status_list = get_status_list(contract)
    for status_item in status_list:
        status_item.delete()


def get_status_list(contract: Contrato):
    return StatusContrato.objects.filter(contrato=contract)


def copy_status(target: Contrato, destination: Contrato):
    target_status_list = get_status_list(target)

    # copy status list
    for status_item in target_status_list:
        status_item.contrato = destination
        status_item.pk = None
        status_item.save()
        # change the pk to None and save the object acts like a clone

    # update status field
    destination.status = target.status
    destination.save(update_fields=['status'])

    # update products status fields
    if destination.tipo_produto == 17:  # PORT + REFIN
        copy_port_status(target, destination)
        copy_refin_status(target, destination)

    # adicione aqui trativas para outros tipos de produto


def copy_port_status(target: Contrato, destination: Contrato):
    target_port = Portabilidade.objects.get(contrato=target)
    destination_port = Portabilidade.objects.get(contrato=destination)
    destination_port.status = target_port.status
    destination_port.save(update_fields=['status'])


def copy_refin_status(target: Contrato, destination: Contrato):
    target_refin = Refinanciamento.objects.get(contrato=target)
    destination_refin = Refinanciamento.objects.get(contrato=destination)
    destination_refin.status = target_refin.status
    destination_refin.save(update_fields=['status'])
