from contract.constants import EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus


def run():
    ids = [62277, 61088, 60620, 57817, 52705, 52193, 58502, 57569, 61419, 58497]
    target_status = ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value

    for id in ids:
        print('Changing product statuses for contract %d' % id)
        contract = Contrato.objects.get(id=id)

        # adicionar o status aguarda retorno de saldo nos status do contrato
        last_status = contract.last_status
        if last_status.nome == target_status:
            print('.... not necessary to add a status to ContratoStatus list')
        else:
            StatusContrato.objects.create(contrato=contract, nome=target_status)
            print('.... a new status was added to ContratoStatus list')

        # change PORT status
        if (
            contract.tipo_produto == EnumTipoProduto.PORTABILIDADE
            or contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
        ):
            port: Portabilidade = contract.contrato_portabilidade.first()
            port.status = target_status
            port.save(update_fields=['status'])
            print('.... port status was changed')

        # change REFIN status
        if contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            refin: Refinanciamento = contract.contrato_refinanciamento.first()
            refin.status = target_status
            refin.save(update_fields=['status'])
            print('.... refin status was changed')
