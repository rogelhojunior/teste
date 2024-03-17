import logging
from datetime import datetime, timedelta

from django.conf import settings

from contract.constants import EnumContratoStatus, EnumSeguradoras, EnumTipoProduto
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    RetornoSaque,
    SaqueComplementar,
)
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.services.insurance.insurance_agreement import InsuranceDataAgent
from contract.services.payment.payment_manager import PaymentManager
from core.utils import alterar_status
from handlers.criar_dados_planos import escrever_arquivo_generali
from handlers.dock_formalizacao import ajustes_financeiros_estorno
from handlers.tem_saude import adesao, gerar_token_zeus

logger = logging.getLogger('digitacao')


def processa_contrato(contrato, cartao_beneficio, cliente, cliente_cartao, user):
    payment_manager = PaymentManager(
        contract=contrato, user=user, benefit_card=cartao_beneficio
    )
    payment_manager.process_payment(cliente, check_commissioning=True)
    if settings.ENVIRONMENT != 'PROD':
        cliente = contrato.cliente
        insurance_data_agent = InsuranceDataAgent(contrato, cliente)
        for plano in contrato.contrato_planos_contratados.filter():
            logger.info(f'Plano gerado: {plano}')
            logger.info(f'Enum da seguradora: : {plano.plano.seguradora.nome}')
            try:
                if plano.plano.seguradora.nome == EnumSeguradoras.TEM_SAUDE:
                    insurance_data_agent.contract_tem_saude_insurance(plano)
                elif plano.plano.seguradora.nome == EnumSeguradoras.GENERALI:
                    logger.info('Inicio da geração GENERALI')
                    escrever_arquivo_generali(
                        contrato, plano.plano, cartao_beneficio, cliente_cartao
                    )
                    logger.info('Fim da adesao GENERALI')
                elif plano.plano.seguradora.nome == EnumSeguradoras.SABEMI:
                    insurance_data_agent.contract_sabemi_insurance(plano)
            except Exception as e:
                logger.error(
                    f'Error processando plano {plano.plano.seguradora.nome}: {e}'
                )
                print(f'Error processando plano {plano.plano.seguradora.nome}: {e}')
    else:
        for plano in contrato.contrato_planos_contratados.filter():
            logger.info(f'Plano gerado: {plano}')
            logger.info(f'Enum da seguradora: : {plano.plano.seguradora.nome}')
            try:
                if plano.plano.seguradora.nome == EnumSeguradoras.TEM_SAUDE:
                    logger.info('Inicio da geração TEM SEGURO')
                    token = gerar_token_zeus()
                    adesao(cliente, token, contrato, plano.plano)
                    logger.info('Fim da adesao TEM SAUDE')
                elif plano.plano.seguradora.nome == EnumSeguradoras.GENERALI:
                    logger.info('Inicio da geração GENERALI')
                    escrever_arquivo_generali(
                        contrato, plano.plano, cartao_beneficio, cliente_cartao
                    )
                    logger.info('Fim da adesao GENERALI')
            except Exception as e:
                logger.error(
                    f'Error processando plano {plano.plano.seguradora.nome}: {e}'
                )
                print(f'Error processando plano {plano.plano.seguradora.nome}: {e}')


def verificar_saques_pendentes():
    tres_dias_atras = datetime.now() - timedelta(days=3)
    saques_pendentes = SaqueComplementar.objects.filter(
        data_solicitacao__lte=tres_dias_atras,
        status=ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
    )
    for saque in saques_pendentes:
        if RetornoSaque.objects.filter(contrato=saque.contrato).exists():
            retorno_saque_status = RetornoSaque.objects.get(
                contrato=saque.contrato
            ).Status
            if retorno_saque_status.upper() in ('REP', 'PEN'):
                ajustes_financeiros_estorno(saque.contrato.pk, saque.pk)
        else:
            ajustes_financeiros_estorno(saque.contrato.pk, saque.pk)


def verificar_proposta_sem_solicitacao_de_correcao():
    # Se em 48 do ultimo retorno não ocorrer a solicitação de correção
    dois_dias_atras = datetime.now() - timedelta(days=2)
    contratos_status = StatusContrato.objects.filter(
        data_fase_inicial__lte=dois_dias_atras,
        nome=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
    )

    contratos_ids = contratos_status.values_list('contrato_id', flat=True)
    contratos = Contrato.objects.filter(id__in=contratos_ids)

    for contrato in contratos:
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            contrato_saque = CartaoBeneficio.objects.get(contrato=contrato)
            if (
                contrato_saque.status
                == ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
            ):
                alterar_status(
                    contrato,
                    contrato_saque,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
                )
        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
            if (
                contrato_saque.status
                == ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
            ):
                alterar_status(
                    contrato,
                    contrato_saque,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
                )


def get_contract_reproved_status() -> tuple:
    return (
        ContractStatus.REPROVADA_POLITICA_INTERNA.value,
        ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
        ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
        ContractStatus.REPROVADA_MESA_CORBAN.value,
        ContractStatus.SALDO_REPROVADO.value,
        ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
        ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
    )
