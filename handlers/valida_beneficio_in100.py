from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.especie import EspecieIN100
from contract.products.portabilidade.views import (
    get_status_reprovacao,
    validar_regra_especie,
)


class ValidadorBeneficio:
    def __init__(self, contrato, in100):
        self.contrato = contrato
        self.in100 = in100
        self.analise_beneficio = {
            'aprovada': False,
            'in100_retornada': False,
            'motivo': '-',
        }
        self.status = StatusContrato.objects.filter(contrato=contrato).last()
        self.STATUS_REPROVACAO = get_status_reprovacao()

    def validar(self):
        if self.in100.retornou_IN100:
            self._validar_in100_retornada()
        else:
            self.analise_beneficio['aprovada'] = True
        return self.analise_beneficio

    def _validar_in100_retornada(self):
        self.analise_beneficio['in100_retornada'] = True
        print(self.status)
        if (
            not EspecieIN100.objects.filter(
                numero_especie=self.in100.cd_beneficio_tipo
            ).exists()
            and self.status.nome not in self.STATUS_REPROVACAO
        ):
            self.analise_beneficio['aprovada'] = False
            self.analise_beneficio['motivo'] = 'Especie não cadastrada'
        elif (
            self.in100.situacao_beneficio in ['INELEGÍVEL', 'BLOQUEADA', 'BLOQUEADO']
            and self.status.nome not in self.STATUS_REPROVACAO
        ):
            self.analise_beneficio['aprovada'] = False
            self.analise_beneficio['motivo'] = 'Beneficio não cadastrado'
        elif self.in100.cd_beneficio_tipo in {4, 5, 6, 32, 33, 34, 51, 83, 87, 92}:
            self._validar_especie()
        elif (
            self.status.nome
            not in self.STATUS_REPROVACAO + [ContractStatus.FORMALIZACAO_CLIENTE.value]
            and not StatusContrato.objects.filter(
                contrato=self.contrato, nome=ContractStatus.FORMALIZACAO_CLIENTE.value
            ).exists()
        ):
            self.analise_beneficio['aprovada'] = True
            self.analise_beneficio['motivo'] = '-'

    def _validar_especie(self):
        resposta = validar_regra_especie(
            self.in100.cd_beneficio_tipo,
            self.in100.cliente,
            self.in100.numero_beneficio,
        )
        if resposta['regra_aprovada']:
            if (
                self.status.nome
                not in self.STATUS_REPROVACAO
                + [ContractStatus.FORMALIZACAO_CLIENTE.value]
                and not StatusContrato.objects.filter(
                    contrato=self.contrato,
                    nome=ContractStatus.FORMALIZACAO_CLIENTE.value,
                ).exists()
            ):
                self.analise_beneficio['aprovada'] = True
                self.analise_beneficio['motivo'] = '-'

        elif self.status.nome not in self.STATUS_REPROVACAO:
            self.analise_beneficio['aprovada'] = False
            self.analise_beneficio['motivo'] = 'Fora da Politica'
