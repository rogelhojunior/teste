from datetime import datetime
from typing import Optional

from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.especie import EspecieIN100
from contract.products.portabilidade.utils import (
    anos_de_beneficio,
    calcular_idade_anos_meses_dias,
    idade_na_concessao,
    meses_de_beneficio,
)
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from core.models.parametro_produto import ParametrosProduto
from custom_auth.models import UserProfile


# Função para adicionar um status de cancelado no contrato(REPROVAR CONTRATO)
def atualizar_contrato_portabilidade(
    contract: Contrato,
    contract_status: int,
    portability_status: int,
    table_description: str,
    user: Optional[UserProfile] = None,
):
    # update Contrato status
    contract.status = contract_status
    contract.save(update_fields=['status'])

    # update Portabildiade status
    portabilidade: Portabilidade = Portabilidade.objects.filter(
        contrato=contract
    ).first()
    portabilidade.status = portability_status
    portabilidade.save(update_fields=['status'])

    # create StatusContrato record
    StatusContrato.objects.create(
        contrato=contract,
        nome=portability_status,
        descricao_mesa=table_description,
        created_by=user,
    )


# Por causa da repetição dos status foi criada uma função get para retorno dos status de reprovacao
def get_status_reprovacao() -> list[int, int, int, int, int, int]:
    return [
        ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
        ContractStatus.INT_AGUARDA_AVERBACAO.value,
        ContractStatus.INT_AVERBACAO_PENDENTE.value,
        ContractStatus.INT_FINALIZADO.value,
        ContractStatus.REPROVADO.value,
        ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
    ]


# Função que verifica os beneficios da IN100
# quando são retornados na API de Envio de LINK
# Quando o contrato ja foi criado
def status_envio_link_portabilidade(contrato, user):
    in100 = DadosIn100.objects.filter(numero_beneficio=contrato.numero_beneficio).last()
    status = StatusContrato.objects.filter(contrato=contrato).last()
    portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
    STATUS_REPROVACAO = get_status_reprovacao()
    if in100.retornou_IN100:
        especie = EspecieIN100.objects.filter(
            numero_especie=in100.cd_beneficio_tipo
        ).exists()

        if not especie and status.nome not in STATUS_REPROVACAO:
            atualizar_contrato_portabilidade(
                contrato,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO.value,
                f'{in100.cd_beneficio_tipo} - Especie não cadastrada',
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()

        elif (
            in100.situacao_beneficio in ['INELEGÍVEL', 'BLOQUEADA', 'BLOQUEADO']
            and status.nome not in STATUS_REPROVACAO
        ):
            atualizar_contrato_portabilidade(
                contrato,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO.value,
                'Beneficio bloqueado ou cessado',
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()

        elif in100.cd_beneficio_tipo in {4, 5, 6, 32, 33, 34, 51, 83, 87, 92}:
            resposta = validar_regra_especie(
                in100.cd_beneficio_tipo, in100.cliente, in100.numero_beneficio
            )
            if resposta['regra_aprovada']:
                if (
                    status.nome
                    not in STATUS_REPROVACAO
                    + [ContractStatus.FORMALIZACAO_CLIENTE.value]
                    and not StatusContrato.objects.filter(
                        contrato=contrato,
                        nome=ContractStatus.FORMALIZACAO_CLIENTE.value,
                    ).exists()
                ):
                    if portabilidade.insercao_sem_sucesso:
                        msg = 'proposta não INSERIDA valide com o Suporte'
                    else:
                        msg = '-'
                    atualizar_contrato_portabilidade(
                        contrato,
                        EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                        ContractStatus.FORMALIZACAO_CLIENTE.value,
                        msg,
                        user,
                    )

            elif status.nome not in STATUS_REPROVACAO:
                atualizar_contrato_portabilidade(
                    contrato,
                    EnumContratoStatus.CANCELADO,
                    ContractStatus.REPROVADO.value,
                    'Fora da Politica',
                )
                RefuseProposalFinancialPortability(contrato=contrato).execute()
        elif status.nome not in STATUS_REPROVACAO + [
            ContractStatus.FORMALIZACAO_CLIENTE.value
        ]:
            if not StatusContrato.objects.filter(
                contrato=contrato, nome=ContractStatus.FORMALIZACAO_CLIENTE.value
            ).exists():
                if portabilidade.insercao_sem_sucesso:
                    msg = 'proposta não INSERIDA valide com o Suporte'
                else:
                    msg = '-'
                atualizar_contrato_portabilidade(
                    contrato,
                    EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                    ContractStatus.FORMALIZACAO_CLIENTE.value,
                    msg,
                    user,
                )

    elif status.nome not in STATUS_REPROVACAO + [
        ContractStatus.AGUARDANDO_RETORNO_IN100.value
    ]:
        cliente_in100 = DadosIn100.objects.filter(
            numero_beneficio=contrato.numero_beneficio
        ).first()
        msg = cliente_in100.chamada_sem_sucesso or '-'
        atualizar_contrato_portabilidade(
            contrato,
            EnumContratoStatus.DIGITACAO,
            ContractStatus.AGUARDANDO_RETORNO_IN100.value,
            msg,
            user,
        )


def status_retorno_in100(cliente, user, tipo_beneficio) -> None:
    # TODO: Retirar a condicional e colocar apenas o status reprovação e o for no começo da função
    # Pois so entra no for se estiver no status de contrato especifico
    if not Contrato.objects.filter(cliente=cliente).exists():
        return
    contratos = Contrato.objects.filter(
        cliente=cliente,
        contrato_portabilidade__status__in=[
            ContractStatus.AGUARDA_ENVIO_LINK.value,
            ContractStatus.AGUARDANDO_RETORNO_IN100.value,
        ],
    )
    STATUS_REPROVACAO = get_status_reprovacao()
    for contrato in contratos:
        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            portabilidade = Portabilidade.objects.get(contrato=contrato)
            in100 = DadosIn100.objects.filter(
                numero_beneficio=contrato.numero_beneficio
            ).last()
            if in100.vr_disponivel_emprestimo and in100.vr_disponivel_emprestimo < 0:
                contrato.status = EnumContratoStatus.CANCELADO
                contrato.save()
                portabilidade.status = ContractStatus.REPROVADO.value
                portabilidade.save()
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.REPROVADO.value,
                    descricao_mesa='Valor total disponível pra emprestimo negativo',
                )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.get(contrato=contrato)
                    refin.status = portabilidade.status
                    refin.save()
                RefuseProposalFinancialPortability(contrato=contrato).execute()
            elif in100.retornou_IN100 and in100.in100_data_autorizacao_:
                status = StatusContrato.objects.filter(contrato=contrato).last()
                especie = EspecieIN100.objects.filter(
                    numero_especie=tipo_beneficio
                ).exists()

                if not especie and status.nome not in STATUS_REPROVACAO:
                    atualizar_contrato_portabilidade(
                        contrato,
                        EnumContratoStatus.CANCELADO,
                        ContractStatus.REPROVADO.value,
                        f'{tipo_beneficio} - Especie não cadastrada',
                    )
                elif (
                    in100.situacao_beneficio in ['INELEGÍVEL', 'BLOQUEADA', 'BLOQUEADO']
                    and status.nome not in STATUS_REPROVACAO
                ):
                    atualizar_contrato_portabilidade(
                        contrato,
                        EnumContratoStatus.CANCELADO,
                        ContractStatus.REPROVADO.value,
                        'Beneficio bloqueado ou cessado',
                    )
                    RefuseProposalFinancialPortability(contrato=contrato).execute()
                elif in100.cd_beneficio_tipo in {
                    4,
                    5,
                    6,
                    32,
                    33,
                    34,
                    51,
                    83,
                    87,
                    92,
                }:
                    resposta = validar_regra_especie(
                        in100.cd_beneficio_tipo, in100.cliente, in100.numero_beneficio
                    )
                    if resposta['regra_aprovada']:
                        if (
                            status.nome
                            not in STATUS_REPROVACAO
                            + [ContractStatus.FORMALIZACAO_CLIENTE.value]
                            and not StatusContrato.objects.filter(
                                contrato=contrato,
                                nome=ContractStatus.FORMALIZACAO_CLIENTE.value,
                            ).exists()
                        ):
                            msg = portabilidade.insercao_sem_sucesso or '-'
                            atualizar_contrato_portabilidade(
                                contrato,
                                EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                                ContractStatus.FORMALIZACAO_CLIENTE.value,
                                msg,
                                user,
                            )
                    elif status.nome not in STATUS_REPROVACAO:
                        atualizar_contrato_portabilidade(
                            contrato,
                            EnumContratoStatus.CANCELADO,
                            ContractStatus.REPROVADO.value,
                            'Fora da Politica',
                        )
                        RefuseProposalFinancialPortability(contrato=contrato).execute()
                elif status.nome not in STATUS_REPROVACAO + [
                    ContractStatus.FORMALIZACAO_CLIENTE.value
                ]:
                    if not StatusContrato.objects.filter(
                        contrato=contrato,
                        nome=ContractStatus.FORMALIZACAO_CLIENTE.value,
                    ).exists():
                        msg = portabilidade.insercao_sem_sucesso or '-'
                        atualizar_contrato_portabilidade(
                            contrato,
                            EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                            ContractStatus.FORMALIZACAO_CLIENTE.value,
                            msg,
                            user,
                        )
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                refin = Refinanciamento.objects.get(contrato=contrato)
                portabilidade.refresh_from_db()
                refin.status = portabilidade.status
                refin.save()


# Função para validar as especies de acordo com as regras estabelecidas
def validar_regra_especie(numero_especie, cliente, numero_beneficio):
    resposta = {'regra_aprovada': True}
    parametro_morte = (
        ParametrosProduto.objects.filter(tipoProduto=EnumTipoProduto.PORTABILIDADE)
        .first()
        .idade_especie_87
    )

    data_nascimento = cliente.dt_nascimento
    idade_anos, idade_meses, idade_dias = calcular_idade_anos_meses_dias(
        data_nascimento
    )

    data_concessao_beneficio = (
        DadosIn100.objects.filter(numero_beneficio=numero_beneficio)
        .last()
        .dt_expedicao_beneficio
    )
    if not data_concessao_beneficio:
        resposta['regra_aprovada'] = False
        resposta['motivo'] = 'não possui data de concessão'
        return resposta
    anos_beneficio = anos_de_beneficio(data_concessao_beneficio)

    def set_resposta_aprovada(flag, motivo=''):
        resposta['regra_aprovada'] = flag
        if motivo:
            resposta['motivo'] = 'Fora da Politica'

    if numero_especie in {4, 5, 6, 32, 33, 34, 51, 83, 92}:
        if idade_anos < 55:
            set_resposta_aprovada(False, '-')
        elif 55 <= idade_anos < 59:
            if anos_beneficio < 15:
                set_resposta_aprovada(False, '-')
        elif idade_anos == 59 and (
            idade_meses < 11 or (idade_meses == 11 and idade_dias < 29)
        ):
            if anos_beneficio < 15:
                set_resposta_aprovada(False, '-')
        elif idade_anos > 59:
            pass

    elif numero_especie == 87 and idade_anos >= parametro_morte:
        set_resposta_aprovada(False, '-')

    return resposta


def validacao_regra_morte(contrato):
    resposta = {'regra_aprovada': True}
    portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
    parcelas = portabilidade.numero_parcela_atualizada
    data_nascimento = contrato.cliente.dt_nascimento
    dados_IN100 = DadosIn100.objects.filter(
        numero_beneficio=contrato.numero_beneficio
    ).last()
    data_concessao_beneficio = dados_IN100.dt_expedicao_beneficio
    numero_especie = dados_IN100.cd_beneficio_tipo

    if not data_concessao_beneficio:
        return {'regra_aprovada': False, 'motivo': 'não possui data de concessão'}

    meses_beneficio = meses_de_beneficio(data_concessao_beneficio)
    idade_concessao = idade_na_concessao(data_nascimento, data_concessao_beneficio)
    data_limite = datetime.strptime('2015-06-17', '%Y-%m-%d').date()

    def set_resposta_aprovada(flag, motivo=''):
        resposta['regra_aprovada'] = flag
        if motivo:
            resposta['motivo'] = 'Fora da Politica'

    if numero_especie in {2, 21, 93}:
        limites_idade = []
        duracoes = []

        if data_concessao_beneficio < data_limite:
            pass
        elif data_concessao_beneficio.year < 2021:
            limites_idade = [21, 27, 30, 41, 44]
            duracoes = [3, 6, 10, 15, 20]
        else:
            limites_idade = [22, 28, 31, 42, 45]
            duracoes = [3, 6, 10, 15, 20]

        idade_dentro_limites = False
        for i, limite in enumerate(limites_idade):
            if idade_concessao < limite:
                idade_dentro_limites = True
                duracao_beneficio = duracoes[i] * 12 - meses_beneficio
                if duracao_beneficio < parcelas:
                    motivo = '-'
                    set_resposta_aprovada(False, motivo)
                break
        if not idade_dentro_limites:
            resposta['regra_aprovada'] = True
            resposta['motivo'] = '-'
    return resposta
