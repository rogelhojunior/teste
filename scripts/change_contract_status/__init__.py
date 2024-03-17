from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.constants import ContractStatus


def run():
    ids = [
        # put here the ids you want
    ]
    # change the status yo uwant
    status = ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value

    for id in ids:
        contract = Contrato.objects.get(id=id)
        contract.status = status
        contract.save(update_fields=['status'])
        print('Status changed for contract %d' % id)
