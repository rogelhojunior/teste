import logging

from contract.models import contratos as Contrato
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.inss_beneficio import INSSBeneficioTipo
from contract.products.consignado_inss.models.log_webhook_qitech import LogWebHookQiTech
from core.models import Cliente
from handlers.webhook_qitech import atualiza_contrato_webhook, traduzir_campo

logger = logging.getLogger('digitacao')


def criar_log_webhook(json_obj, nome_funcao):
    chave_financeira = json_obj['key']
    contrato = Contrato.objects.get(chaveWebHookFinanceira=chave_financeira)
    log = LogWebHookQiTech.objects.create(contrato=contrato)
    log.nome_funcao_webhook = nome_funcao
    log.chave_retorno_financeira = chave_financeira
    log.json_entrada = str(json_obj)
    log.save()
    return log


def receber_webhook_consulta_saldo(json_obj, user):
    chave_financeira = json_obj['key']
    contrato = Contrato.objects.get(chaveWebHookFinanceira=chave_financeira)
    if json_obj['proposal_key']:
        atualiza_contrato_webhook(json_obj, user)
    dadosIn100, _ = DadosIn100.objects.get_or_create(
        cliente=contrato.cliente, numero_beneficio=contrato.numero_beneficio
    )

    dadosIn100.nome_cliente = json_obj['data']['name']

    flSituacaoBeneficio = json_obj['data']['benefit_status'] == 'eligible'
    dadosIn100.situacao_beneficio = flSituacaoBeneficio

    beneficioTipo = INSSBeneficioTipo.objects.get(
        dsINSSBeneficioTipoIngles=json_obj['data']['assistance_type']
    )

    dadosIn100.cd_beneficio_tipo = beneficioTipo.cdInssBeneficioTipo
    dadosIn100.uf_beneficio = json_obj['data']['state']
    tipoCredito = None
    if json_obj['data']['credit_type'] == 'checking_account':
        tipoCredito = 1
    elif json_obj['data']['credit_type'] == 'magnetic_card':
        tipoCredito = 4
    dadosIn100.cd_tipo_conta = tipoCredito

    cdBanco = json_obj['data']['disbursement_bank_account']['bank_code']
    dadosIn100.codigo_banco = int(cdBanco) if cdBanco.isdigit() else None

    nuAgencia = json_obj['data']['disbursement_bank_account']['account_branch']
    dadosIn100.numero_agencia = int(nuAgencia) if nuAgencia.isdigit() else None

    dadosIn100.numero_conta = json_obj['data']['disbursement_bank_account'][
        'account_number'
    ]
    dadosIn100.numero_digito = json_obj['data']['disbursement_bank_account'][
        'account_digit'
    ]

    situacaoPensao = traduzir_campo(json_obj['data']['alimony'])
    dadosIn100.situacao_pensao = situacaoPensao

    dadosIn100.valor_margem = json_obj['data']['consigned_credit']['balance']
    dadosIn100.qt_total_emprestimos = json_obj['data']['number_of_active_reservations']
    dadosIn100.concessao_judicial = json_obj['data']['has_judicial_concession']

    flPossuiRepresentanteLegal = (
        json_obj['data']['legal_representative'] is not None
        and str(json_obj['data']['legal_representative']['document_number']).isdigit()
    )
    dadosIn100.possui_representante_legal = flPossuiRepresentanteLegal

    dadosIn100.possui_procurador = json_obj['data']['has_power_of_attorney']
    dadosIn100.possui_entidade_representante = json_obj['data'][
        'has_entity_representation'
    ]
    dadosIn100.descricao_recusa = json_obj['key']
    try:
        dadosIn100.ultimo_exame_medico = json_obj['data']['last_inquiry_date'] or None
    except Exception as e:
        logger.error(
            f'Erro ao formatar ultimo_exame_medico (receber_webhook_consulta_saldo): {e}'
        )

    try:
        dadosIn100.dt_expedicao_beneficio = json_obj['data']['grant_date'] or None
    except Exception as e:
        logger.error(
            f'Erro ao formatar dt_expedicao_beneficio (receber_webhook_consulta_saldo): {e}'
        )

    dadosIn100.save()


def obter_margem_cliente(nu_cpf):
    cliente = Cliente.objects.get(nu_cpf=nu_cpf)
    dadosIn100 = DadosIn100.objects.get(cliente=cliente)

    return {'valor_margem': dadosIn100.valor_margem}
