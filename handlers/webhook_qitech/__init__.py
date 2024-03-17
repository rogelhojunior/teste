import json
import logging
import re
import typing
from datetime import datetime

import pytz
import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_404_NOT_FOUND
from translate import Translator

from api_log.constants import EnumStatusCCB
from api_log.models import LogCliente, LogWebhook, QitechRetornos
from contract.constants import EnumContratoStatus, EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
)
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.tasks import retorno_saldo_portabilidade_assync
from contract.products.portabilidade.views import (
    status_retorno_in100,
    validacao_regra_morte,
)
from contract.products.portabilidade_refin.handlers import (
    CancelRefinancing,
)
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
    RefuseProposalFinancialFreeMargin,
)
from contract.services.documents import UploadQiTechDocument, AttachQiTechDocument
from contract.services.payment.portability_collateral_paid import (
    PortabilityRefinancingCollateralPaidProcessor,
    PortabilityCollateralPaidProcessor,
)
from contract.services.persistance.contract import create_contract_status
from contract.services.persistance.products import update_product_status
from core.constants import EnumTipoConta
from core.models import Cliente
from core.models.cliente import DadosBancarios
from core.models.parametro_produto import ParametrosProduto
from core.tasks import insere_proposta_margem_livre_financeira_hub
from custom_auth.models import UserProfile
from handlers.dicionario_beneficios import procura_valor
from handlers.dicionario_dataprev import retorno_erro_dataprev, retorno_sucesso_dataprev
from handlers.insere_proposta_inss_financeira import autenticacao_hub
from handlers.negative_margin_processor import NegativeMarginProcessor
from handlers.submete_proposta_portabilidade import (
    recusa_proposta_portabilidade_financeira_hub,
)
from handlers.validar_regras_beneficio_contrato import (
    ValidadorRegrasBeneficioContratoPortabilidadeRefinanciamento,
)
from simulacao.api.views import SimulateFreeMarginContract
from simulacao.communication import qitech
from simulacao.constants import EnumContaTipo
from .enums import QiTechEndorsementErrorEnum

from .qitech_webhook_disbursement import QiTechWebhookDisbursementData
from .QiTechWebhookData import QiTechWebhookData
from .QiTechWebhookPaymentFailedData import (
    QiTechWebhookPaymentFailedData,
    QiTechWebhookPaymentFailedDataRefinancing,
)
from .qitech_webhook_disbursement import QiTechWebhookDisbursementData
from .validators.information_pending_approval import (
    ProposalInformationPendingApprovalValidator,
)
from .validators.portability_proposal import PortabilityProposalValidator

STATUS_BENEFICIO = {
    ContractStatus.AGUARDANDO_RETORNO_IN100.value,
    ContractStatus.FORMALIZACAO_CLIENTE.value,
    ContractStatus.AGUARDANDO_IN100_RECALCULO,
}


def convert_score(x):
    return 0.005 * x + 0.5


def salvando_retorno_IN100_contrato(in100, especie):
    """
    Função que irá verificar se a in100 já retornou e salvará o numero do
    beneficio e a especie na aba de Portabilidade do Contrato.
    """

    from contract.products.portabilidade.api.views import (
        aceita_proposta_automatica_qitech_cip,
    )

    if contratos := Contrato.objects.filter(cliente=in100.cliente).exists():
        contratos = Contrato.objects.filter(cliente=in100.cliente)

        if in100.valor_margem and in100.valor_margem < 0:
            negative_margin_processor = NegativeMarginProcessor(
                in100=in100,
                product_type=EnumTipoProduto.PORTABILIDADE,
            )
            negative_margin_processor.execute()

        if in100.validacao_in100_recalculo:
            for contrato in contratos:
                ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
                if (
                    ultimo_status
                    and ultimo_status.nome
                    == ContractStatus.AGUARDANDO_IN100_RECALCULO.value
                ):
                    # Criar um novo status de contrato
                    portabilidade = Portabilidade.objects.filter(
                        contrato=contrato
                    ).first()
                    portabilidade.numero_beneficio = in100.numero_beneficio
                    portabilidade.especie = especie
                    contrato.status = EnumContratoStatus.MESA
                    contrato.save()
                    portabilidade.status = (
                        ContractStatus.RETORNO_IN100_RECALCULO_RECEBIDO.value
                    )
                    portabilidade.save()
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.RETORNO_IN100_RECALCULO_RECEBIDO.value,
                        descricao_mesa='Retorno da in100 No recalculo recebido com SUCESSO',
                    )
                    """Quando a aprovação automática estiver ativa, tentará aprovar os contratos"""
                    parametro_produto = ParametrosProduto.objects.filter(
                        tipoProduto=contrato.tipo_produto
                    ).first()
                    if parametro_produto.aprovar_automatico:
                        aceita_proposta_automatica_qitech_cip(contrato)
        else:
            for contrato in contratos:
                if contrato.tipo_produto in {
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                }:
                    portabilidade = Portabilidade.objects.filter(
                        contrato=contrato
                    ).first()
                    portabilidade.numero_beneficio = in100.numero_beneficio
                    portabilidade.especie = especie
                    portabilidade.save()

                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                        and in100.retornou_IN100
                    ):
                        refinancing = contrato.contrato_refinanciamento.first()
                        is_valid = ValidadorRegrasBeneficioContratoPortabilidadeRefinanciamento(
                            contrato=contrato,
                            dados_in100=in100,
                            refinancing=refinancing,
                        ).validar()
                        error_message = ''
                        if not is_valid.get('regra_aprovada'):
                            error_message = is_valid.get('motivo')
                        elif (
                            refinancing.dt_ultimo_pagamento
                            and in100.data_expiracao_beneficio
                            and (
                                refinancing.dt_ultimo_pagamento
                                > in100.data_expiracao_beneficio
                            )
                        ):
                            error_message = (
                                'Prazo do empréstimo maior que o prazo do benefício'
                            )

                        if error_message:
                            CancelRefinancing(
                                refinancing=refinancing,
                                reason=error_message,
                            ).execute()
                    elif (
                        contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE
                        and portabilidade.dt_ultimo_pagamento
                        and in100.data_expiracao_beneficio
                        and (
                            portabilidade.dt_ultimo_pagamento
                            > in100.data_expiracao_beneficio
                        )
                    ):
                        update_product_status(product=portabilidade)
                        create_contract_status(
                            contract=contrato,
                            mesa_description='Prazo do empréstimo maior que o prazo do benefício',
                        )

                elif contrato.tipo_produto in (
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.INSS,
                ):
                    ultimo_status = StatusContrato.objects.filter(
                        contrato=contrato
                    ).last()
                    if (
                        ultimo_status
                        and ultimo_status.nome
                        == ContractStatus.AGUARDANDO_RETORNO_IN100.value
                        and contrato.cliente.endereco_cep
                    ):
                        cliente = contrato.cliente
                        margem_livre = MargemLivre.objects.filter(
                            contrato=contrato
                        ).first()
                        parametros_produto = ParametrosProduto.objects.filter(
                            tipoProduto=EnumTipoProduto.MARGEM_LIVRE
                        ).first()

                        error_message = ''
                        # Valida margem livre negativa
                        if in100.valor_margem <= 0:
                            error_message = 'Você não possui margem disponível para realizar um novo contrato'
                        elif (
                            margem_livre.dt_vencimento_ultima_parcela
                            and in100.data_expiracao_beneficio
                            and (
                                margem_livre.dt_vencimento_ultima_parcela
                                > in100.data_expiracao_beneficio
                            )
                        ):
                            error_message = (
                                'Prazo do empréstimo maior que o prazo do benefício'
                            )

                        if error_message:
                            update_product_status(product=margem_livre)
                            create_contract_status(
                                contract=contrato,
                                mesa_description=error_message,
                            )
                            # Skips to next contract from iteration
                            continue

                        if in100.valor_margem < margem_livre.vr_parcelas:
                            # Passa 2 vezes o valor da margem pois quando a parcela é menor que o valor da margem, a parcela fica com o valor da amrgem
                            margem_livre.valor_parcela_recalculada = float(
                                in100.valor_margem
                            )
                            margem_livre.save()
                            validador = SimulateFreeMarginContract()
                            (
                                simulacao_obj,
                                _,
                            ) = validador.simular_contrato(
                                cliente.dt_nascimento,
                                in100.cd_beneficio_tipo,
                                in100.valor_margem,
                                margem_livre.vr_contrato,
                                in100.valor_margem,  # novo valor das parcelas
                                float(parametros_produto.taxa_proposta_margem_livre)
                                / 100,
                                contrato.cd_contrato_tipo,
                                contrato.tipo_produto,
                            )
                            for opcoes in simulacao_obj.opcoes_contrato:
                                if opcoes.qt_parcelas == margem_livre.qtd_parcelas:
                                    contrato.taxa_efetiva_mes = float(
                                        round(opcoes.tx_efetiva_mes * 100, 4)
                                    )
                                    contrato.taxa_efetiva_ano = float(
                                        round(opcoes.tx_efetiva_ano * 100, 4)
                                    )
                                    contrato.vr_iof = float(opcoes.vr_iof)
                                    margem_livre.vr_parcelas = in100.valor_margem
                                    margem_livre.vr_contrato = float(opcoes.vr_contrato)
                                    margem_livre.vr_liberado_cliente = float(
                                        opcoes.vr_liberado_cliente
                                    )
                                    margem_livre.dt_vencimento_primeira_parcela = (
                                        opcoes.dt_vencimento_primeira_parcela
                                    )
                                    margem_livre.dt_vencimento_ultima_parcela = (
                                        opcoes.dt_vencimento_ultima_parcela
                                    )
                                    margem_livre.save()
                                    # TODO verificar se pode dar break nessa condicional

                        insere_proposta_margem_livre_financeira_hub(
                            contrato,
                            float(contrato.taxa_efetiva_mes) / 100,
                            'calendar_days',
                            float(parametros_produto.multa_contrato_margem_livre) / 100,
                        )

                        # Busca a margem livre novamente e reprova caso necessário
                        margem_livre.refresh_from_db()

                        if (
                            margem_livre.dt_vencimento_ultima_parcela
                            and in100.data_expiracao_beneficio
                            and (
                                margem_livre.dt_vencimento_ultima_parcela
                                > in100.data_expiracao_beneficio
                            )
                        ):
                            update_product_status(product=margem_livre)
                            create_contract_status(
                                contract=contrato,
                                mesa_description='Prazo do empréstimo maior que o prazo do benefício',
                            )
                            # Skips to next contract from iteration
                            continue


def traduzir_campo(valor):
    """Função que irá traduzir os valores  retornados do payload da IN100"""
    valor = valor.replace('_', ' ')
    if valor in ['elegible', 'Elegible', 'ELEGIBLE']:
        return 'ELEGÍVEIS'
    elif valor in ['inelegible', 'Inelegible', 'INELEGIBLE']:
        return 'INELEGÍVEL'
    elif valor in ['blocked', 'Blocked', 'BLOCKED']:
        return 'BLOQUEADO'
    elif valor in ['not payer', 'Not payer', 'Not Payer', 'NOT PAYER']:
        return 'NÃO PAGADOR'
    elif valor in ['payer', 'Payer', 'PAYER']:
        return 'PAGADOR'
    elif valor in ['benefit', 'Benefit', 'BENEFIT']:
        return 'BENEFÍCIO'
    elif valor in ['not found', 'Not found', 'Not Found', 'not Found', 'NOT FOUND']:
        return 'NÃO ENCONTRADO'
    else:
        translator = Translator(to_lang='pt')
        return translator.translate(valor).upper()


def recebe_retorno_IN100(data):
    """Função que irá converter os valores retornados da IN100 para as respectivas variáveis"""
    key = data.get('key', {})
    status_beneficio = traduzir_campo(data.get('data', {}).get('benefit_status', {}))
    nome_beneficiario = data.get('data', {}).get('name', {})
    estado_beneficiario = data.get('data', {}).get('state', {})
    pensao_alimenticia = traduzir_campo(data.get('data', {}).get('alimony', {}))
    tem_concessao_judicial = data.get('data', {}).get('has_judicial_concession', {})
    tem_representacao_entidade = data.get('data', {}).get(
        'has_entity_representation', {}
    )
    tem_procurador = data.get('data', {}).get('has_power_of_attorney', {})
    data_concessao = data.get('data', {}).get('grant_date', {})
    aniversario_beneficiario = data.get('data', {}).get('birth_date', {})
    tipo_beneficio = data.get('data', {}).get('assistance_type', {})
    valor_liquido_beneficio = (
        data.get('data', {}).get('benefit_card', {}).get('limit', {})
    )
    margem_livre_cartao_beneficio = (
        data.get('data', {}).get('benefit_card', {}).get('balance', {})
    )
    limite_cartao_beneficio = (
        data.get('data', {}).get('benefit_card', {}).get('limit', {})
    )
    margem_livre_cartao_consignado = (
        data.get('data', {}).get('consigned_card', {}).get('balance', {})
    )
    limite_cartao_consignado = (
        data.get('data', {}).get('consigned_card', {}).get('limit', {})
    )
    margem_livre_credito_consignado = (
        data.get('data', {}).get('consigned_credit', {}).get('balance', {})
    )
    conta_banco = (
        data.get('data', {}).get('disbursement_bank_account', {}).get('bank_code', {})
    )
    conta_agencia = (
        data.get('data', {})
        .get('disbursement_bank_account', {})
        .get('account_branch', {})
    )
    vr_disponivel_emprestimo = (
        data.get('data', {}).get('consigned_credit', {}).get('balance', {})
    )

    situacao_beneficio = data.get('data', {}).get('benefit_situation', {})
    data_final_beneficio = data.get('data', {}).get('benefit_end_date', {})
    data_expiracao_beneficio = data.get('data', {}).get(
        'benefit_quota_expiration_date', {}
    )
    data_expiracao_beneficio = (
        datetime.fromisoformat(data_expiracao_beneficio).date()
        if data_expiracao_beneficio
        else None
    )

    margem_total_beneficio = data.get('data', {}).get('social_benefit_max_balance', {})
    data_retorno_in100 = data.get('event_datetime', {})
    valor_beneficio = (margem_total_beneficio * 100) / 45
    qtd_emprestimos = data.get('data', {}).get('number_of_active_reservations', {})
    qt_total_emprestimos_suspensos = data.get('data', {}).get(
        'number_of_suspended_reservations', {}
    )

    return [
        key,  # 0
        status_beneficio,  # 1
        nome_beneficiario,  # 2
        estado_beneficiario,  # 3
        aniversario_beneficiario,  # 4
        tipo_beneficio,  # 5
        valor_beneficio,  # 6
        valor_liquido_beneficio,  # 7
        margem_livre_credito_consignado,  # 8
        conta_banco,  # 9
        conta_agencia,  # 10
        pensao_alimenticia,  # 11
        tem_concessao_judicial,  # 12
        tem_representacao_entidade,  # 13
        data_concessao,  # 14
        tem_procurador,  # 15
        vr_disponivel_emprestimo,  # 16
        margem_livre_cartao_beneficio,  # 17
        limite_cartao_beneficio,  # 18
        margem_livre_cartao_consignado,  # 19
        limite_cartao_consignado,  # 20
        situacao_beneficio,  # 21
        data_final_beneficio,  # 22
        data_expiracao_beneficio,  # 23
        data_retorno_in100,  # 24
        margem_total_beneficio,  # 25
        qtd_emprestimos,  # 26
        qt_total_emprestimos_suspensos,  # 27
    ]


def atribuindo_valor_in100(data, in100, tipo_beneficio, lista_retorno):
    """Função que irá atribuir os valores do retorno da in100 pros casos de Conta Corrente e Cartão Magnético"""
    """Dados do cliente da in100"""
    in100.cliente.nome_cliente = lista_retorno[2]
    in100.cliente.endereco_uf = lista_retorno[3]
    in100.cliente.dt_nascimento = data.date()
    in100.cliente.salario_liquido = lista_retorno[7]
    in100.cliente.save()

    """Dados da IN100"""
    in100.uf_beneficio = lista_retorno[3]
    in100.situacao_beneficio = lista_retorno[1]
    in100.cd_beneficio_tipo = int(tipo_beneficio)
    in100.valor_margem = lista_retorno[8]
    in100.valor_beneficio = lista_retorno[6]
    in100.valor_liquido = lista_retorno[7]
    if in100.validacao_in100_saldo_retornado:
        in100.validacao_in100_recalculo = True
    in100.retornou_IN100 = True
    in100.situacao_pensao = lista_retorno[11]
    in100.concessao_judicial = lista_retorno[12]
    in100.possui_entidade_representante = lista_retorno[13]
    in100.dt_expedicao_beneficio = lista_retorno[14]
    in100.possui_procurador = lista_retorno[15]
    in100.vr_disponivel_emprestimo = lista_retorno[16]
    in100.margem_livre_cartao_beneficio = lista_retorno[17]
    in100.limite_cartao_beneficio = lista_retorno[18]
    in100.margem_livre_cartao_consignado = lista_retorno[19]
    in100.limite_cartao_consignado = lista_retorno[20]
    in100.beneficio_ativo = lista_retorno[21]
    in100.data_final_beneficio = lista_retorno[22]
    in100.data_expiracao_beneficio = lista_retorno[23]
    in100.data_retorno_in100 = lista_retorno[24]
    in100.margem_total_beneficio = lista_retorno[25]
    in100.qt_total_emprestimos = lista_retorno[26]
    in100.qt_total_emprestimos_suspensos = lista_retorno[27]
    in100.save()


def atualiza_contrato_webhook(data, user):
    from contract.products.portabilidade.utils import validar_faixa_idade
    from contract.constants import STATUS_REPROVADOS

    data_atual = timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')
    qi_tech_data = QiTechWebhookData(data)

    LogWebhook.objects.create(
        chamada_webhook=f'WEBHOOK QITECH {data_atual}', log_webhook=data
    )
    logger = logging.getLogger('webhookqitech')
    user = UserProfile.objects.get(identifier='30620610000159')

    try:
        if data.get('webhook_type') == 'social_security_balance_request':
            status = data.get('status')
            if status == 'failure':
                """Caso de falha no retorno da IN100"""
                key = data['key']
                in100 = DadosIn100.objects.get(balance_request_key=key)

                in100.descricao_recusa = data['data']['description']
                in100.save()
                log_api_id, _ = LogCliente.objects.get_or_create(cliente=in100.cliente)
                QitechRetornos.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=in100.cliente,
                    retorno=data,
                    tipo=data['webhook_type'],
                )
                message = f'Falha na Consulta da IN100 ({in100.cliente.nome_cliente}) - {in100.descricao_recusa}'
                logger.error(message, extra={'extra': data})
                if data['data']['enumerator'] == 'inexistent_benefit':
                    if Contrato.objects.filter(
                        cliente=in100.cliente,
                        numero_beneficio=in100.numero_beneficio,
                    ).exists():
                        contratos = Contrato.objects.filter(
                            cliente=in100.cliente,
                            numero_beneficio=in100.numero_beneficio,
                        )
                        for contrato in contratos:
                            if contrato.tipo_produto in {
                                EnumTipoProduto.PORTABILIDADE,
                                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                            }:
                                portabilidade = Portabilidade.objects.get(
                                    contrato=contrato
                                )
                                if portabilidade.status in STATUS_BENEFICIO:
                                    portabilidade.status = (
                                        ContractStatus.REPROVADO.value
                                    )
                                    portabilidade.save(update_fields=['status'])
                                    contrato.status = EnumContratoStatus.CANCELADO
                                    contrato.save()
                                    StatusContrato.objects.create(
                                        contrato=contrato,
                                        nome=ContractStatus.REPROVADO.value,
                                        descricao_mesa='O BENEFICIO não foi encontrado',
                                    )
                                    if (
                                        contrato.tipo_produto
                                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                                    ):
                                        refin = Refinanciamento.objects.get(
                                            contrato=contrato
                                        )
                                        refin.status = ContractStatus.REPROVADO.value
                                        refin.save(update_fields=['status'])
                            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                                margem_livre = MargemLivre.objects.get(
                                    contrato=contrato
                                )
                                if margem_livre.status in STATUS_BENEFICIO:
                                    margem_livre.status = ContractStatus.REPROVADO.value
                                    margem_livre.save(update_fields=['status'])
                                    StatusContrato.objects.create(
                                        contrato=contrato,
                                        nome=ContractStatus.REPROVADO.value,
                                        descricao_mesa='O BENEFICIO não foi encontrado',
                                    )
                        return
                return
            """Caso de Sucesso no retorno da IN100"""
            data_bank_accout = data.get('data', {}).get('disbursement_bank_account', {})
            conta_digito = data_bank_accout.get('account_digit')
            lista_retorno = recebe_retorno_IN100(data)
            in100 = DadosIn100.objects.get(balance_request_key=lista_retorno[0])

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=in100.cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=in100.cliente,
                retorno=data,
                tipo=data['webhook_type'],
            )
            cartao_magnetico = data.get('data', {}).get('credit_type', {})
            if cartao_magnetico == 'magnetic_card':
                """Quando o retorno é Cartão Magnético"""
                data = datetime.strptime(lista_retorno[4], '%d%m%Y')
                DadosBancarios.objects.update_or_create(
                    cliente=in100.cliente,
                    conta_banco=lista_retorno[9],
                    conta_tipo=EnumTipoConta.CARTAO_MAGNETICO,
                    defaults={
                        'conta_agencia': lista_retorno[10],
                        'retornado_in100': True,
                    },
                )
                tipo_beneficio = procura_valor(lista_retorno[5])
                if not tipo_beneficio:
                    logger.info(f'{in100.cliente.id_unico} - Beneficio não encontrado.')
                else:
                    atribuindo_valor_in100(data, in100, tipo_beneficio, lista_retorno)
                    salvando_retorno_IN100_contrato(in100, tipo_beneficio)
                    in100.tipo_retorno = 'Cartão Magnético'
                    in100.save()
                    logger.info(
                        f'{in100.cliente.id_unico} - IN100 Consultada com Sucesso.'
                    )
                    status_retorno_in100(in100.cliente, user, tipo_beneficio)
            else:
                """Quando o retorno é Conta Corrente"""
                conta_numero = data_bank_accout.get('account_number')
                data = datetime.strptime(lista_retorno[4], '%d%m%Y')
                pessoa_juridica = lista_retorno[12]
                if pessoa_juridica:
                    conta_tipo = EnumContaTipo.CONTACORRENTEPESSOALJURIDICA.value
                else:
                    conta_tipo = EnumContaTipo.CONTACORRENTEPESSOALFISICA.value
                if DadosBancarios.objects.filter(
                    cliente=in100.cliente,
                    conta_banco=lista_retorno[9],
                    conta_tipo=conta_tipo,
                ).exists():
                    dado_bancario = DadosBancarios.objects.filter(
                        cliente=in100.cliente,
                        conta_banco=lista_retorno[9],
                        conta_tipo=conta_tipo,
                    ).last()
                    dado_bancario.conta_digito = conta_digito
                    dado_bancario.conta_numero = conta_numero
                    dado_bancario.conta_agencia = lista_retorno[10]
                    dado_bancario.retornado_in100 = True
                    dado_bancario.save()
                else:
                    DadosBancarios.objects.create(
                        cliente=in100.cliente,
                        conta_banco=lista_retorno[9],
                        conta_tipo=conta_tipo,
                        conta_digito=conta_digito,
                        conta_numero=conta_numero,
                        conta_agencia=lista_retorno[10],
                        retornado_in100=True,
                    )
                # DadosBancarios.objects.update_or_create(
                #     cliente=in100.cliente,
                #     conta_banco=lista_retorno[9],
                #     conta_tipo=conta_tipo,
                #     defaults={
                #         'conta_digito': conta_digito,
                #         'conta_numero': conta_numero,
                #         'conta_agencia': lista_retorno[10],
                #         'retornado_in100': True,
                #     },
                # )
                tipo_beneficio = procura_valor(lista_retorno[5])
                if not tipo_beneficio:
                    logger.info(f'{in100.cliente.id_unico} - Beneficio não encontrado.')
                else:
                    atribuindo_valor_in100(data, in100, tipo_beneficio, lista_retorno)
                    salvando_retorno_IN100_contrato(in100, tipo_beneficio)
                    in100.tipo_retorno = 'Conta Corrente'
                    in100.save()
                    logger.info(
                        f'{in100.cliente.id_unico} - IN100 Consultada com Sucesso.'
                    )
                    status_retorno_in100(in100.cliente, user, tipo_beneficio)
            return
        if qi_tech_data.is_payment_failure():
            QiTechWebhookPaymentFailedData(
                data,
            ).execute(logger)
        elif qi_tech_data.is_portability_refinancing_canceled():
            refinancing = Refinanciamento.objects.get(
                chave_proposta=data.get('proposal_key')
            )
            QiTechWebhookPaymentFailedDataRefinancing(
                data=data,
                refinancing=refinancing,
            ).execute()
        elif qi_tech_data.is_disbursed_debt():
            qi_tech_disbursement_data = QiTechWebhookDisbursementData(data)
            qi_tech_disbursement_data.set_contract_records()
            qi_tech_disbursement_data.process_incoming_data()
            qi_tech_disbursement_data.create_qi_tech_log_records()
            qi_tech_disbursement_data.log_message(logger)
        elif 'proposal_status' in data:
            try:
                portabilidade = Portabilidade.objects.get(
                    chave_proposta=data['proposal_key']
                )
            except Portabilidade.DoesNotExist as e:
                raise ValidationError(
                    detail={
                        'error': f'Contrato de portabilidade com a chave {data["proposal_key"]} não encontrado.'
                    },
                    code=HTTP_404_NOT_FOUND,
                ) from e

            contrato = portabilidade.contrato
            if not StatusContrato.objects.filter(
                contrato=contrato, nome__in=STATUS_REPROVADOS
            ).exists():
                cliente = contrato.cliente
                if data['proposal_status'] == 'rejected':
                    motivo = data['data']['error']['description']
                    portabilidade.status_ccb = EnumStatusCCB.REJECTED.value
                    portabilidade.motivo_recusa = motivo
                    portabilidade.dt_recusa_retido = datetime.now()
                    portabilidade.status = ContractStatus.REPROVADO.value
                    portabilidade.save()

                    contrato.status = EnumContratoStatus.CANCELADO
                    contrato.save()

                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    user = UserProfile.objects.get(identifier=user.identifier)
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.REPROVADO.value,
                        descricao_mesa='Contrato REJEITADO pela QITECH',
                        created_by=user,
                    )
                    if settings.ENVIRONMENT == 'PROD':
                        recusa_proposta_portabilidade_financeira_hub(contrato, 'DELETE')
                    else:
                        RefuseProposalFinancialPortability(contrato=contrato).execute()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Rejeitado pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})
                    # Recusa a proposta de refinanciamento
                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        CancelRefinancing(
                            refinancing=Refinanciamento.objects.get(contrato=contrato),
                            reason=motivo,
                        ).execute()

                elif data['proposal_status'] == 'pending_acceptance':
                    numero_portabilidade = data['data']['portability_number']

                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    portabilidade.numero_portabilidade_CTC_CIP = numero_portabilidade
                    portabilidade.status_ccb = EnumStatusCCB.PENDING_ACCEPTANCE.value
                    portabilidade.save()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Esperando ACEITE.'
                    )
                    logger.info(message, extra={'extra': data})

                elif data['proposal_status'] == 'accepted':
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Saldo Retornado pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})
                    # Validate portability proposal data cpf, benefit_number and contract_number
                    user = UserProfile.objects.get(identifier=user.identifier)
                    PortabilityProposalValidator(portability=portabilidade).execute(
                        user=user
                    )

                    if (
                        not StatusContrato.objects.filter(
                            contrato=contrato, nome=ContractStatus.SALDO_RETORNADO.value
                        ).exists()
                        and not StatusContrato.objects.filter(
                            contrato=contrato,
                            nome=ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
                        ).exists()
                        and not StatusContrato.objects.filter(
                            contrato=contrato,
                            nome__in=STATUS_REPROVADOS,
                        ).exists()
                    ):
                        parametros_produto = ParametrosProduto.objects.filter(
                            tipoProduto=contrato.tipo_produto
                        ).first()
                        saldo_devedor = data['data']['final_due_balance']
                        numero_portabilidade = data['data']['portability_number']
                        taxa_contrato_original = data['data']['original_contract'][
                            'interest'
                        ]
                        numero_parcela_atualizada = data['data']['original_contract'][
                            'opened_installment_number'
                        ]
                        valor_parcela_original = data['data']['original_contract'][
                            'installment_face_value'
                        ]
                        numero_parcelas_atrasadas = data['data']['original_contract'][
                            'overdue_installment_number'
                        ]

                        log_api_id, _ = LogCliente.objects.get_or_create(
                            cliente=contrato.cliente
                        )
                        QitechRetornos.objects.create(
                            log_api_id=log_api_id.pk,
                            cliente=contrato.cliente,
                            retorno=data,
                            tipo=data['proposal_status'],
                        )

                        portabilidade.saldo_devedor_atualizado = saldo_devedor
                        portabilidade.taxa_contrato_original = taxa_contrato_original
                        portabilidade.numero_parcela_atualizada = (
                            numero_parcela_atualizada
                        )
                        portabilidade.numero_portabilidade = numero_portabilidade
                        portabilidade.valor_parcela_original = valor_parcela_original
                        portabilidade.numero_parcelas_atrasadas = (
                            numero_parcelas_atrasadas
                        )
                        portabilidade.save()
                        contrato_portabilidade = Portabilidade.objects.get(
                            contrato=contrato
                        )
                        contrato_portabilidade.status = (
                            ContractStatus.SALDO_RETORNADO.value
                        )
                        contrato_portabilidade.dt_recebimento_saldo_devedor = (
                            datetime.now()
                        )
                        contrato_portabilidade.save()
                        user = UserProfile.objects.get(identifier=user.identifier)
                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=ContractStatus.SALDO_RETORNADO.value,
                            descricao_mesa='Recebido Webhook de SALDO da QITECH',
                            created_by=user,
                        )
                        resposta = validacao_regra_morte(contrato)
                        if numero_parcelas_atrasadas > 0:
                            msg = 'Parcelas atrasadas'
                            if settings.ENVIRONMENT == 'PROD':
                                recusa_proposta_portabilidade_financeira_hub(
                                    contrato, 'DELETE'
                                )
                            else:
                                RefuseProposalFinancialPortability(
                                    contrato=contrato
                                ).execute()
                            portabilidade.status = (
                                ContractStatus.REPROVADA_POLITICA_INTERNA.value
                            )
                            portabilidade.save()
                            user = UserProfile.objects.get(identifier=user.identifier)
                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                                descricao_mesa='Contrato possui parcelas em aberto no banco origem',
                                created_by=user,
                            )
                            ValidacaoContrato.objects.update_or_create(
                                contrato=contrato,
                                mensagem_observacao=msg,
                                defaults={
                                    'checked': False,
                                    'retorno_hub': 'Contrato possui parcelas em aberto no banco origem',
                                },
                            )
                        elif saldo_devedor < parametros_produto.valor_minimo_emprestimo:
                            msg = 'Valor Minimo CCB(Portabilidade)'
                            if settings.ENVIRONMENT == 'PROD':
                                recusa_proposta_portabilidade_financeira_hub(
                                    contrato, 'DELETE'
                                )
                            else:
                                RefuseProposalFinancialPortability(
                                    contrato=contrato
                                ).execute()
                            portabilidade.status = (
                                ContractStatus.REPROVADA_POLITICA_INTERNA.value
                            )
                            portabilidade.save()
                            user = UserProfile.objects.get(identifier=user.identifier)
                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                                descricao_mesa='Reprovado na fase do RECALCULO',
                                created_by=user,
                            )
                            ValidacaoContrato.objects.update_or_create(
                                contrato=contrato,
                                mensagem_observacao=msg,
                                defaults={
                                    'checked': False,
                                    'retorno_hub': 'Reprovado no RECALCULO: valor do CONTRATO menor que o minimo',
                                },
                            )

                        elif saldo_devedor > parametros_produto.valor_maximo_emprestimo:
                            msg = 'Valor Maximo CCB(Portabilidade)'
                            if settings.ENVIRONMENT == 'PROD':
                                recusa_proposta_portabilidade_financeira_hub(
                                    contrato, 'DELETE'
                                )
                            else:
                                RefuseProposalFinancialPortability(
                                    contrato=contrato
                                ).execute()
                            portabilidade.status = (
                                ContractStatus.REPROVADA_POLITICA_INTERNA.value
                            )
                            portabilidade.save()
                            user = UserProfile.objects.get(identifier=user.identifier)
                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                                descricao_mesa='Reprovado na fase do RECALCULO',
                                created_by=user,
                            )
                            ValidacaoContrato.objects.update_or_create(
                                contrato=contrato,
                                mensagem_observacao=msg,
                                defaults={
                                    'checked': False,
                                    'retorno_hub': 'Reprovado no RECALCULO: valor do CONTRATO maior que o maximo',
                                },
                            )
                        elif not resposta['regra_aprovada']:
                            if settings.ENVIRONMENT == 'PROD':
                                recusa_proposta_portabilidade_financeira_hub(
                                    contrato, 'DELETE'
                                )
                            else:
                                RefuseProposalFinancialPortability(
                                    contrato=contrato
                                ).execute()
                            portabilidade.status = (
                                ContractStatus.REPROVADA_POLITICA_INTERNA.value
                            )
                            portabilidade.save()
                            user = UserProfile.objects.get(identifier=user.identifier)
                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                                descricao_mesa='Fora da Politica',
                                created_by=user,
                            )
                            ValidacaoContrato.objects.update_or_create(
                                contrato=contrato,
                                mensagem_observacao=resposta['motivo'],
                                defaults={
                                    'checked': False,
                                    'retorno_hub': f"{resposta['motivo']}",
                                },
                            )
                        else:
                            resposta_faixa_idade = validar_faixa_idade(contrato)
                            if not resposta_faixa_idade['regra_aprovada']:
                                contrato_portabilidade.status = (
                                    ContractStatus.REPROVADO.value
                                )
                                contrato_portabilidade.save()
                                user = UserProfile.objects.get(
                                    identifier=user.identifier
                                )
                                StatusContrato.objects.create(
                                    contrato=contrato,
                                    nome=ContractStatus.REPROVADO.value,
                                    created_by=user,
                                    descricao_mesa=resposta_faixa_idade['motivo'],
                                )
                            else:
                                # Após arrumar a função retorno_saldo_portabilidade, retornar o valor da parcela recalculada
                                retorno_saldo_portabilidade_assync.delay(
                                    contrato.token_contrato,
                                    saldo_devedor,
                                    user.identifier,
                                    numero_parcela_atualizada,
                                    valor_parcela_original,
                                )

                                logger.info(
                                    f'{cliente.id_unico} - Contrato({contrato.pk}): RECALCULO REALIZADO'
                                )

                elif data['proposal_status'] == 'canceled':
                    portabilidade.status_ccb = EnumStatusCCB.CANCELED.value
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    portabilidade.status = ContractStatus.REPROVADO.value
                    portabilidade.save()
                    contrato.status = EnumContratoStatus.CANCELADO

                    contrato.save()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Cancelado pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})
                    contrato_portabilidade = Portabilidade.objects.get(
                        contrato=contrato
                    )
                    # Criar um novo status de contrato
                    contrato_portabilidade.status = ContractStatus.REPROVADO.value
                    contrato_portabilidade.save()

                    user = UserProfile.objects.get(identifier=user.identifier)
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.REPROVADO.value,
                        descricao_mesa='Recebido o webhook de CANCELADO da QITECH',
                        created_by=user,
                    )

                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        CancelRefinancing(
                            refinancing=Refinanciamento.objects.get(contrato=contrato),
                            reason='Recebido o webhook de CANCELADO da QITECH',
                        ).execute()

                elif data['proposal_status'] == 'retained':
                    motivo = data['data']['retained_reason']['description']
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Saldo RETIDO pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})

                    portabilidade.status_ccb = EnumStatusCCB.RETAINED.value
                    portabilidade.motivo_recusa = motivo
                    portabilidade.dt_recusa_retido = datetime.now()
                    contrato.status = EnumContratoStatus.CANCELADO
                    contrato.save()
                    portabilidade.status = ContractStatus.REPROVADO.value
                    portabilidade.save()

                    user = UserProfile.objects.get(identifier=user.identifier)
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.REPROVADO.value,
                        descricao_mesa='Recebido o webhook de RETIDO da QITECH',
                        created_by=user,
                    )

                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        CancelRefinancing(
                            refinancing=Refinanciamento.objects.get(contrato=contrato),
                            reason=motivo,
                        ).execute()

                elif data['proposal_status'] == 'settlement_sent':
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    portabilidade.status_ccb = EnumStatusCCB.SETTLEMENT_SENT.value
                    portabilidade.banco_atacado = data['data']['receipt'][
                        'destination'
                    ]['name']
                    portabilidade.save()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'LIQUIDAÇÃO enviada pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})

                elif data['proposal_status'] == 'pending_settlement_confirmation':
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    portabilidade.status_ccb = (
                        EnumStatusCCB.PENDING_SETTLMENTE_CONFIMATION.value
                    )
                    portabilidade.save()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'LIQUIDAÇÃO PENDENTE enviada pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})

                elif data['proposal_status'] == 'paid':
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=data['proposal_status'],
                    )
                    logger.info(
                        f'{cliente.id_unico} - Contrato({contrato.pk}): retornado pago pela QITECH .\n Payload{data}'
                    )
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'PAGO pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})

                    portabilidade.status_ccb = EnumStatusCCB.PAID.value
                    portabilidade.save(update_fields=['status_ccb'])
                    contrato.status = EnumContratoStatus.PAGO
                    contrato.contrato_pago = True
                    contrato.dt_pagamento_contrato = datetime.now()
                    contrato.save(
                        update_fields=[
                            'status',
                            'contrato_pago',
                            'dt_pagamento_contrato',
                        ]
                    )

                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        PortabilityRefinancingCollateralPaidProcessor(
                            contract=contrato,
                            portability=portabilidade,
                            refinancing=Refinanciamento.objects.get(contrato=contrato),
                            user=user,
                        ).execute(process_type='paid')
                    elif contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                        PortabilityCollateralPaidProcessor(
                            contract=contrato,
                            portability=portabilidade,
                            user=user,
                        ).execute(process_type='paid')

                    else:
                        raise NotImplementedError

        elif data.get('webhook_type') == 'credit_transfer.proposal.credit_operation':
            credit_data = data['data']
            if credit_data['credit_operation_type'] == 'refinancing':
                refinanciamento = Refinanciamento.objects.get(
                    chave_proposta=data['proposal_key']
                )
                if credit_data['credit_operation_status'] == 'disbursed':
                    contrato = refinanciamento.contrato
                    cliente = contrato.cliente
                    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
                    refinanciamento.flag_sucessfully_disbursed_proposal()
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                        tipo=credit_data['credit_operation_status'],
                    )
                    contrato.status = EnumContratoStatus.PAGO
                    contrato.save()
                    refinanciamento.status = (
                        ContractStatus.INT_FINALIZADO_DO_REFIN.value
                    )
                    refinanciamento.save()
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.INT_FINALIZADO_DO_REFIN.value,
                        descricao_mesa='Recebido o webhook de desembolso do refinanciamento pela QITECH',
                    )
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'Refinanciamento desembolsado  pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})

        elif 'status' in data:
            if data['status'] == 'canceled_permanently':
                margem_livre = MargemLivre.objects.filter(
                    chave_proposta=data['key']
                ).first()
                contrato = margem_livre.contrato
                if not StatusContrato.objects.filter(
                    contrato=contrato, nome__in=STATUS_REPROVADOS
                ).exists():
                    cliente = contrato.cliente
                    log_api_id, _ = LogCliente.objects.get_or_create(
                        cliente=contrato.cliente
                    )
                    QitechRetornos.objects.create(
                        log_api_id=log_api_id.pk,
                        cliente=contrato.cliente,
                        retorno=data,
                    )
                    margem_livre.status = ContractStatus.REPROVADO.value
                    margem_livre.save()
                    contrato.status = EnumContratoStatus.CANCELADO
                    contrato.save()
                    message = (
                        f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                        f'DESAVERBADO pela QITECH.'
                    )
                    logger.info(message, extra={'extra': data})
                    user = UserProfile.objects.get(identifier=user.identifier)
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.REPROVADO.value,
                        descricao_mesa='Recebido o webhook de DESAVERBADO da QITECH',
                        created_by=user,
                    )
        elif 'collateral_type' in data:
            """Retorno do Dataprev (caso de sucesso e caso de falha)"""
            in100 = DadosIn100.objects.filter(
                numero_beneficio=data.get('collateral_data', {}).get('benefit_number')
            ).last()
            contratos = Contrato.objects.filter(cliente=in100.cliente).exists()
            if contratos:
                contratos = Contrato.objects.filter(cliente=in100.cliente)
                date_format = '%Y-%m-%dT%H:%M:%SZ'
                for contrato in contratos:
                    if not StatusContrato.objects.filter(
                        contrato=contrato, nome__in=STATUS_REPROVADOS
                    ).exists():
                        enumerator_data = data.get('collateral_data', {}).get(
                            'last_response'
                        )

                        log_api_id, _ = LogCliente.objects.get_or_create(
                            cliente=contrato.cliente
                        )
                        QitechRetornos.objects.create(
                            log_api_id=log_api_id.pk,
                            cliente=contrato.cliente,
                            retorno=data,
                            tipo=data['collateral_type'],
                        )
                        message = (
                            f'{in100.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                            f'RETORNO DATAPREV.'
                        )
                        logger.info(message, extra={'extra': data})
                        codigo = None
                        descricao = None
                        if 'success' in enumerator_data:
                            codigo, descricao = retorno_sucesso_dataprev(
                                data.get('collateral_data', {})
                                .get('last_response', {})
                                .get('success', [{}])[0]
                                .get('enumerator')
                            )
                        elif 'errors' in enumerator_data:
                            codigo, descricao = retorno_erro_dataprev(
                                data.get('collateral_data', {})
                                .get('last_response', {})
                                .get('errors', [{}])[0]
                                .get('enumerator')
                            )
                        date_string = data.get('collateral_data', {}).get(
                            'last_response_event_datetime'
                        )
                        if contrato.tipo_produto is EnumTipoProduto.PORTABILIDADE:
                            """Salvando o retorno se o contrato for de Portabilidade"""
                            portabilidade = Portabilidade.objects.filter(
                                contrato=contrato
                            ).first()
                            portabilidade.codigo_dataprev = codigo
                            portabilidade.descricao_dataprev = descricao
                            portabilidade.dt_retorno_dataprev = datetime.strptime(
                                date_string, date_format
                            )
                            portabilidade.save()
                        elif contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE:
                            """Salvando o retorno se o contrato for de Margem Livre"""
                            margem_livre = MargemLivre.objects.filter(
                                contrato=contrato
                            ).first()
                            margem_livre.codigo_dataprev = codigo
                            margem_livre.descricao_dataprev = descricao
                            margem_livre.dt_retorno_dataprev = datetime.strptime(
                                date_string, date_format
                            )
                            margem_livre.save()
                            if (
                                margem_livre.codigo_dataprev
                                in (
                                    'IE',
                                    'AN',
                                    'HX',
                                    'IF',
                                    'AV',
                                    'OF',
                                    'IA',
                                    'OS',
                                    'AY',
                                    'HZ',
                                    'AP',
                                    'GA',
                                    'BC',
                                    'NC',
                                    'NB',
                                    'CA',
                                    'HR',
                                    'PV',
                                    'IR',
                                )
                                and margem_livre.status
                                is not ContractStatus.REPROVADO.value
                            ):
                                margem_livre.status = ContractStatus.REPROVADO.value
                                margem_livre.save()
                                contrato.status = EnumContratoStatus.CANCELADO
                                contrato.save()
                                StatusContrato.objects.create(
                                    contrato=contrato,
                                    nome=ContractStatus.REPROVADO.value,
                                    descricao_mesa='Caso de erro Dataprev',
                                    created_by=user,
                                )
                                RefuseProposalFinancialFreeMargin(contrato).execute()

        elif 'data' in data:
            if 'collateral_type' in data['data'] and (
                data['data']['collateral_type'] == 'social_security'
            ):
                is_constituted = data['data']['collateral_constituted']
                if is_constituted:
                    if (
                        'credit_operation_type' in data['data']
                        and data['data']['credit_operation_type'] == 'portability'
                    ):
                        portabilidade = Portabilidade.objects.get(
                            chave_proposta=data['proposal_key']
                        )
                        contrato = portabilidade.contrato
                        cliente = contrato.cliente
                        # Salva o log do contrato
                        log_api_id, _ = LogCliente.objects.get_or_create(
                            cliente=contrato.cliente
                        )
                        QitechRetornos.objects.create(
                            log_api_id=log_api_id.pk,
                            cliente=contrato.cliente,
                            retorno=data,
                            tipo=data['data']['collateral_type'],
                        )
                        logger.info(
                            f'{cliente.id_unico} - Contrato({contrato.pk}): transação finalizada pela QITECH.\n Payload {data}'
                        )
                        message = (
                            f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                            f'LIQUIDAÇÃO PENDENTE enviada pela QITECH.'
                        )
                        logger.info(message, extra={'extra': data})
                        # Salva os dados da portabilidade
                        portabilidade.status_ccb = EnumStatusCCB.COLLATERAL.value
                        portabilidade.save(
                            update_fields=[
                                'status_ccb',
                            ]
                        )
                        # Caso seja port ou port+refin define o status e caso contrário, dá raise de erro.

                        # Salva os dados do contrato
                        contrato.status = EnumContratoStatus.PAGO
                        contrato.save(update_fields=['status'])

                        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                            PortabilityCollateralPaidProcessor(
                                contract=contrato,
                                portability=portabilidade,
                                user=user,
                            ).execute(process_type='collateral')

                        elif (
                            contrato.tipo_produto
                            == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                        ):
                            PortabilityRefinancingCollateralPaidProcessor(
                                contract=contrato,
                                portability=portabilidade,
                                refinancing=Refinanciamento.objects.get(
                                    contrato=contrato
                                ),
                                user=user,
                            ).execute(process_type='collateral')

                    elif (
                        'credit_operation_type' in data['data']
                        and data['data']['credit_operation_type'] == 'refinancing'
                    ):
                        refinanciamento = Refinanciamento.objects.get(
                            chave_proposta=data['proposal_key']
                        )
                        contrato = refinanciamento.contrato
                        cliente = contrato.cliente
                        log_api_id, _ = LogCliente.objects.get_or_create(
                            cliente=cliente
                        )
                        refinanciamento.flag_sucessfully_finalized_proposal()
                        log_api_id, _ = LogCliente.objects.get_or_create(
                            cliente=contrato.cliente
                        )
                        QitechRetornos.objects.create(
                            log_api_id=log_api_id.pk,
                            cliente=contrato.cliente,
                            retorno=data,
                            tipo=data['data']['collateral_type'],
                        )
                        refinanciamento.status = (
                            ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value
                        )
                        refinanciamento.dt_averbacao = datetime.now()
                        refinanciamento.save()
                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value,
                            descricao_mesa='Recebido o webhook de averbação do refinanciamento pela QITECH',
                        )
                        message = (
                            f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                            f'REFINANCIAMENTO AVERBADO pela QITECH.'
                        )
                        logger.info(message, extra={'extra': data})
                    elif 'key' in data:
                        margem_livre = MargemLivre.objects.get(
                            chave_proposta=data['key']
                        )
                        contrato = margem_livre.contrato
                        if not StatusContrato.objects.filter(
                            contrato=contrato, nome__in=STATUS_REPROVADOS
                        ).exists():
                            cliente = contrato.cliente
                            log_api_id, _ = LogCliente.objects.get_or_create(
                                cliente=contrato.cliente
                            )
                            QitechRetornos.objects.create(
                                log_api_id=log_api_id.pk,
                                cliente=contrato.cliente,
                                retorno=data,
                                tipo=data['data']['collateral_type'],
                            )
                            message = (
                                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                                f'TRANSAÇÃO DE AVERBADA pela QITECH.'
                            )
                            logger.info(message, extra={'extra': data})
                            contrato.status = EnumContratoStatus.PAGO
                            contrato.save()
                            contrato_margem_livre = MargemLivre.objects.get(
                                contrato=contrato
                            )
                            # Criar um novo status de contrato
                            contrato.status = EnumContratoStatus.PAGO
                            contrato.save()
                            contrato_margem_livre.dt_averbacao = datetime.now()
                            contrato_margem_livre.status = (
                                ContractStatus.APROVADA_AVERBACAO.value
                            )
                            contrato_margem_livre.save()

                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.APROVADA_AVERBACAO.value,
                                descricao_mesa='Recebido o webhook de Averbado da QITECH',
                            )
                else:
                    logger.info('Erro averbação: ', extra={'extra': data})
                    error_enumerators = {
                        error['enumerator']
                        for error in data['data']['collateral_data']['last_response'][
                            'errors'
                        ]
                    }
                    ignored_enumerators = {
                        QiTechEndorsementErrorEnum.INVALID_DISBURSEMENT_ACCOUNT,
                        QiTechEndorsementErrorEnum.FIRST_NAME_MISMATCH,
                        QiTechEndorsementErrorEnum.INVALID_STATE,
                        QiTechEndorsementErrorEnum.INVALID_BANK_CODE,
                        QiTechEndorsementErrorEnum.WRONG_BENEFIT_NUMBER_ON_PORTABILITY,
                    }
                    if not error_enumerators.isdisjoint(ignored_enumerators):
                        # If there is an error that is not ignored, call ProposalInformationPendingApprovalValidator
                        ProposalInformationPendingApprovalValidator(
                            payload_webhook=data
                        ).execute()
                    return
        elif 'signed_document_url' in data['data']:
            portabilidade = Portabilidade.objects.get(
                chave_proposta=data['proposal_key']
            )
            contrato = portabilidade.contrato
            if not StatusContrato.objects.filter(
                contrato=contrato, nome__in=STATUS_REPROVADOS
            ).exists():
                cliente = contrato.cliente
                log_api_id, _ = LogCliente.objects.get_or_create(
                    cliente=contrato.cliente
                )
                QitechRetornos.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=contrato.cliente,
                    retorno=data,
                    tipo='Signed',
                )
                message = (
                    f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                    f'ASSINATURA aceita pela QITECH.'
                )
                logger.info(message, extra={'extra': data})

    except ValidationError:
        raise
    except DadosIn100.DoesNotExist as e:
        logger.info(
            '[WEBHOOK QITECH] [IN100] In100 recebida, porém não foi encontrada no sistema.',
            extra={
                'data': data,
            },
        )
        raise ValidationError({
            'erro': 'In100 recebida, porém não foi encontrada no sistema.'
        }) from e
    except Exception as e:
        logger.exception(f'ERRO na chegada do WEBHOOK QITECH({e}) .\n Payload {data}')
        raise ValidationError({
            'erro': 'Houve um erro ao processar os dados recebidos.'
        }) from e


def upload_and_attach_document_to_qitech(
    product: typing.Union[
        Portabilidade,
        Refinanciamento,
        MargemLivre,
    ],
    contract: Contrato,
) -> tuple[requests.Response, dict]:
    # Envia todos os anexos para a QiTech e salva
    for attachment in AnexoContrato.objects.filter(
        contrato=contract,
        tipo_anexo__in=[
            EnumTipoAnexo.CNH,
            EnumTipoAnexo.DOCUMENTO_FRENTE,
            EnumTipoAnexo.DOCUMENTO_VERSO,
            EnumTipoAnexo.SELFIE,
        ],
    ):
        UploadQiTechDocument(
            product=product,
            contract=contract,
            attachment=attachment,
        ).execute()

    return AttachQiTechDocument(
        product=product,
        contract=contract,
        selfie_id=product.document_key_QiTech_Selfie,
        document_identification_id=product.document_key_QiTech_Frente_ou_CNH,
        document_identification_back_id=product.document_key_QiTech_Verso
        or product.document_key_QiTech_Frente_ou_CNH,
    ).execute()


def API_qitech_documentos(token_contrato):
    """API para o envio dos documentos para a QiTech"""
    logger = logging.getLogger('cliente')
    contrato = Contrato.objects.filter(token_contrato=token_contrato).first()

    try:
        if contrato.tipo_produto in [
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ]:
            produto = Portabilidade.objects.get(contrato=contrato)
        elif contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE:
            produto = MargemLivre.objects.get(contrato=contrato)

        response, decoded_response = upload_and_attach_document_to_qitech(
            product=produto, contract=contrato
        )

        cliente = contrato.cliente
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=decoded_response,
            tipo='Attached Documents',
        )
        if response.status_code in [200, 201, 202]:
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f' Documentos Enviados com sucesso para a QITECH.'
            )
            logger.info(message, extra={'extra': decoded_response})
            return True
        else:
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f' Erro ao enviar documentos para a QITECH.'
            )
            logger.error(message, extra={'extra': decoded_response})
            return False

    except Exception as e:
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno={'erro': str(e)},
            tipo='Attached Documents',
        )
        message = (
            f'{contrato.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
            f' Erro ao enviar documentos para a QITECH (Exception).'
        )
        logger.error(message, extra={'extra': e})
        return False


def sign_qitech_product(
    contrato: Contrato,
    product: typing.Union[Refinanciamento, Portabilidade],
    body: dict,
    endpoint: str,
) -> bool:
    """
    Performs QI Tech signature, receives product, dict
    Args:
        contrato: Contrato instance
        product: Product to be signed
        body: Request body
        endpoint: Sign endpoint

    Returns:
        bool: Successful signature or already sent - True,
              Failed to sign (False)
    """
    logger = logging.getLogger('cliente')
    cliente = contrato.cliente
    if not product.sucesso_envio_assinatura:
        integracao_qitech = qitech.QitechApiIntegration()
        json_retorno, status_code = integracao_qitech.execute(
            settings.QITECH_BASE_ENDPOINT_URL,
            endpoint,
            body,
            'POST',
        )
        # Salvando os logs
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
        qitech_retorno = QitechRetornos.objects.create(
            log_api=log_api_id,
            cliente=cliente,
            retorno=json_retorno,
            tipo='Received Signature',
        )
        if status_code in (200, 201, 202):
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f'ASSINATURA enviada para QITECH.'
            )
            logger.info(message, extra={'extra': json_retorno})
            product.sucesso_envio_assinatura = True
        else:
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f'ERRO ao enviar ASSINATURA para QITECH.'
            )
            logger.critical(message, extra={'extra': json_retorno})
            product.sucesso_envio_assinatura = False
            product.motivo_envio_assinatura = f'Erro na API de envio de Assinatura QITECH (400) - QiTechRetorno id: {qitech_retorno.id}'
        product.save()
    return product.sucesso_envio_assinatura


def API_qitech_envio_assinatura(token_contrato):
    """API para o envio da assinatura do cliente para a QiTech para formalizar a operação"""
    logger = logging.getLogger('cliente')
    contrato = Contrato.objects.filter(token_contrato=token_contrato).first()
    cliente = Cliente.objects.filter(contrato=contrato).first()
    if envelope_score := EnvelopeContratos.objects.get(
        token_envelope=contrato.token_envelope
    ).score_unico:
        score_inicial = envelope_score
        score = convert_score(float(score_inicial))
    else:
        score = 0
    try:
        # Salvando o termo e assinatura no anexo do contrato
        anexos = AnexoContrato.objects.filter(contrato=contrato)
        tipos_anexo_permitidos = [
            EnumTipoAnexo.TERMOS_E_ASSINATURAS,
        ]
        for anexo in anexos:
            if (
                anexo.tipo_anexo in tipos_anexo_permitidos
                and (anexo.nome_anexo == 'ccb-Portabilidade')
                and contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE
            ):
                documento_url = anexo.anexo_url
            elif (
                anexo.tipo_anexo in tipos_anexo_permitidos
                and (anexo.nome_anexo == 'ccb-Margem Livre')
                and contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE
            ):
                documento_url = anexo.anexo_url

        # Convertendo para o formato desejado
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        data_hora = contrato.criado_em.astimezone(sao_paulo_tz)
        data_formatada = data_hora.strftime('%Y-%m-%dT%H:%M:%S.%f')[:23] + 'Z'
        formato_desejado = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z'

        if not re.match(formato_desejado, data_formatada):
            data_formatada = f'{data_formatada[:-1]}.000Z'
        data_final = data_formatada
        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            # Envio da Assinatura pra QiTech pro produto Portabilidade
            produto = Portabilidade.objects.get(contrato=contrato)
            body = {
                'type': 'pdf-signature',
                'signed_pdf_path': f'{documento_url}',
                'ip_address': f'{cliente.IP_Cliente}',
                'signature_datetime': f'{data_final}',
                'similarity_score': f'{score}',
                'biometry_analysis_reference': 'SERPRO',
            }
            QITECH_ENDPOINT_ENVIO_ASSINATURA = f'/v2/credit_transfer/proposal/{produto.chave_proposta}/portability_credit_operation/signature'

        elif contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE:
            # Envio da Assinatura pra QiTech pro produto Margem Livre
            produto = MargemLivre.objects.get(contrato=contrato)
            body = {
                'ip_address': f'{cliente.IP_Cliente}',
                'signature_datetime': f'{data_final}',
                'similarity_score': f'{score}',
                'biometry_analysis_reference': 'serpro',
                'type': 'pdf-signature',
                'path-pdf-signed': f'{documento_url}',
            }
            QITECH_ENDPOINT_ENVIO_ASSINATURA = f'/debt/{produto.chave_proposta}/signed'
        elif contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            # Filtra a lista de anexos, apenas pelos anexos permitidos
            anexos_permitidos = anexos.filter(tipo_anexo__in=tipos_anexo_permitidos)

            base_body = {
                'type': 'pdf-signature',
                'ip_address': f'{cliente.IP_Cliente}',
                'signature_datetime': f'{data_final}',
                'similarity_score': f'{score}',
                'biometry_analysis_reference': 'SERPRO',
            }

            anexo_portabilidade = anexos_permitidos.get(nome_anexo='ccb-Portabilidade')

            # Pega a portabilidade e o anexo referente a ccb-Portabilidade
            portabilidade = Portabilidade.objects.get(contrato=contrato)
            retorno_assinatura_portabilidade = sign_qitech_product(
                contrato,
                portabilidade,
                {
                    **base_body,
                    'signed_pdf_path': f'{anexo_portabilidade.anexo_url}',
                },
                f'/v2/credit_transfer/proposal/{portabilidade.chave_proposta}/portability_credit_operation/signature',
            )
            # Verifica se o retorno da Portabilidade deu certo, caso não dê, retorna False
            if not retorno_assinatura_portabilidade:
                return False

            anexo_refinanciamento = anexos_permitidos.get(
                nome_anexo='ccb-Refinanciamento'
            )
            # Pega o refinanciamento e o anexo referente a ccb-Portabilidade + Refinanciamento
            refinanciamento = Refinanciamento.objects.get(contrato=contrato)

            # Finaliza a execução do método
            return sign_qitech_product(
                contrato,
                refinanciamento,
                {
                    **base_body,
                    'signed_pdf_path': f'{anexo_refinanciamento.anexo_url}',
                },
                f'/v2/credit_transfer/proposal/{refinanciamento.chave_proposta}/refinancing_credit_operation/signature',
            )

        if produto.sucesso_envio_assinatura:
            return True
        integracao_desaverbacao = qitech.QitechApiIntegration()
        json_retorno, status_code = integracao_desaverbacao.execute(
            settings.QITECH_BASE_ENDPOINT_URL,
            QITECH_ENDPOINT_ENVIO_ASSINATURA,
            body,
            'POST',
        )
        cliente = contrato.cliente
        # Salvando os logs
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=json_retorno,
            tipo='Received Signature',
        )
        if status_code in (200, 201, 202):
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f' Assinatura enviada com sucesso para a QITECH.'
            )
            logger.info(message, extra={'extra': json_retorno})
            return True
        else:
            message = (
                f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f' Erro ao enviar a assinatura para a QITECH.'
            )
            logger.error(message, extra={'extra': json_retorno})
            return False
    except Exception as e:
        json_formated = str(e)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=json_formated,
            tipo='Received Signature',
        )
        message = (
            f'{cliente.id_unico} - Contrato(ID: {contrato.pk}):'
            f' Erro ao enviar a assinatura para a QITECH (Exception).'
        )
        logger.error(message, extra={'extra': json_formated})
        return False


def envio_termo_in100(
    documento_nome, documento_url, documento_extensao, documento_base_64, anexo, cliente
):
    """
    Realiza a modificação de uma nova proposta na financeira Qi Tech e
    inclui a CCB retornada por eles nos anexos do contrato no nosso banco
    de dados.
    """
    logger = logging.getLogger('cliente')
    try:
        CONST_HUB_FINANCEIRA_QITECH_URL = (
            f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechUpload'
        )

        headers = {
            'Authorization': f'Bearer {autenticacao_hub()}',
            'Content-Type': 'application/json',
        }
        payload = {
            'NmArquivo': f'{documento_nome}.{documento_extensao}',
            'NmUrlArquivo': documento_url,
            'Base64Arquivo': documento_base_64,
        }

        response = requests.post(
            CONST_HUB_FINANCEIRA_QITECH_URL, headers=headers, json=payload
        )
        json_formated = json.loads(response.text)
        json_formated = json.loads(json_formated)
        resposta = {}
        if response.status_code in {200, 201, 202}:
            document_key = json_formated['document_key']
            resposta['retornado'] = True
            resposta['document_key'] = document_key
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                retorno=json_formated,
                tipo='Upload de Documentos',
            )
            logger.info(f'{cliente.id_unico} - Termo IN100 para a QITECH')
        else:
            resposta['retornado'] = False
            resposta['motivo'] = json_formated['translation']
            logger.error(
                f'{cliente.id_unico} - Erro ao enviar o termo IN100 para a QITECH\n Payload{payload}'
            )
        return resposta

    except Exception as e:
        json_formated = e
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            retorno=json_formated,
            tipo='Upload de Documentos',
        )
        logger.error(
            f'{cliente.id_unico} - Erro ao enviar o termo IN100 para a QITECH.{e}\n Payload{payload}'
        )
        return False


def validar_in100_recalculo(contrato):
    from handlers.portabilidade_in100 import consulta_beneficio_in100_portabilidade

    cliente_in100 = DadosIn100.objects.filter(
        numero_beneficio=contrato.numero_beneficio
    ).last()
    cliente_in100.validacao_in100_saldo_retornado = True
    cliente_in100.save()

    resposta = consulta_beneficio_in100_portabilidade(
        contrato.cliente, cliente_in100.numero_beneficio, cliente_in100
    )
    if resposta['retornado']:
        msg = 'IN100 Consultada com sucesso'
    else:
        msg = 'Erro na Chamada IN100'

    contrato_portabilidade = Portabilidade.objects.get(contrato=contrato)
    # Criar um novo status de contrato
    contrato.status = EnumContratoStatus.MESA
    contrato.save(update_fields=['status'])
    StatusContrato.objects.create(
        contrato=contrato,
        nome=ContractStatus.AGUARDANDO_IN100_RECALCULO.value,
        descricao_mesa=msg,
    )
    contrato_portabilidade.status = ContractStatus.AGUARDANDO_IN100_RECALCULO.value
    contrato_portabilidade.save(update_fields=['status'])


def API_qitech_desaverbar_proposta(contrato, status):
    logger = logging.getLogger('digitacao')
    """Realiza a recusa da proposta de margem livre na QITECH"""

    cliente = contrato.cliente

    margem_livre = MargemLivre.objects.get(contrato=contrato)
    proposal_key = margem_livre.chave_proposta
    # Convertendo para o formato desejado
    sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
    data_hora = contrato.criado_em.astimezone(sao_paulo_tz)
    data_final = data_hora.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    body = {
        'key': f'{proposal_key}',
        'data': {},
        'status': 'canceled_permanently',
        'webhook_type': 'debt',
        'event_datetime': f'{data_final}',
    }
    corpo_requisicao = {
        'complex_operation': True,
        'operation_batch': body,
    }
    QITECH_ENDPOINT_DEBT_DESAVERBACAO = (
        f'/debt/{margem_livre.chave_proposta}/cancel_permanently'
    )
    integracao_desaverbacao = qitech.QitechApiIntegration()
    json_retorno, status_code = integracao_desaverbacao.execute(
        settings.QITECH_BASE_ENDPOINT_URL,
        QITECH_ENDPOINT_DEBT_DESAVERBACAO,
        corpo_requisicao,
        'POST',
    )
    try:
        if status_code in {200, 201, 202}:
            margem_livre.sucesso_recusa_proposta = True

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=contrato.cliente,
                retorno=json_retorno,
                tipo=status,
            )
            margem_livre.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
            margem_livre.save()
            logger.info(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}):'
                f'(Margem Livre)Sucesso na desaverbação enviada para QITECH.\n Payload {json_retorno}'
            )
            return True
        else:
            logger.info(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}):'
                f'(Margem Livre)Erro na desaverbação enviada para QITECH.\n Payload {json_retorno}'
            )
            margem_livre.sucesso_recusa_proposta = False
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=contrato.cliente,
                retorno=json_retorno,
                tipo=status,
            )
            margem_livre.motivo_recusa_proposta = (
                f'Status: {status_code}\n' f" Descrição:{json_retorno['title']}"
            )
            margem_livre.save()
            return False
    except Exception as e:
        json_formated = str(e)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=json_formated,
            tipo='Received Signature',
        )
        logger.error(
            f'{cliente.id_unico} - Contrato({contrato.pk}): '
            f'(Margem Livre)Erro ao realizar a Desaverbação da proposta na QiTech.\n Payload{json_retorno}'
        )
        return False
