import json
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone

from api_log.models import LogWebhook
from contract.models.contratos import MargemLivre
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.models.cliente import DadosBancarios

logger = logging.getLogger('digitacao')


def traduzir_tipo_conta(tipo_conta):
    if tipo_conta == 1:
        return 'checking_account'
    elif tipo_conta == 3:
        return 'saving_account'

    else:
        return 'Tipo de conta inválido.'


def separar_numero_ddd(numero_telefone):
    # Remove os caracteres que não são dígitos
    digitos = ''.join(filter(str.isdigit, numero_telefone))

    # Extrai o DDD sem o zero à esquerda (se houver)
    ddd = digitos[:2]
    if ddd.startswith('0'):
        ddd = ddd[1:]

    # Extrai o número de telefone
    numero = digitos[2:]

    # Retorna uma tupla com o DDD e o número de telefone
    return (ddd, numero)


def formatar_cpf(cpf):
    cpf = cpf.replace('.', '').replace('-', '')
    return cpf


def formatar_rg(rg):
    rg = rg.replace('.', '').replace('-', '')  # remove pontos e traços

    return None if len(rg) != 9 else f'{rg[:2]}.{rg[2:5]}.{rg[5:8]}-{rg[8:]}'


def traduzir_sexo(sexo_extenso):
    if sexo_extenso.lower() == 'masculino':
        return 'male'
    elif sexo_extenso.lower() == 'feminino':
        return 'female'
    else:
        return None


def traduzir_estado_civil(estado_civil_extenso):
    if estado_civil_extenso.lower() == 'solteiro(a)':
        return 'single'
    elif estado_civil_extenso.lower() == 'casado(a)':
        return 'married'
    elif estado_civil_extenso.lower() == 'divorciado(a)':
        return 'divorced'
    elif estado_civil_extenso.lower() == 'viúvo(a)':
        return 'widowed'
    else:
        return None


def autenticacao_hub():
    """método que realiza a autenticação no projeto c# do INSS antigo"""

    CONST_AUTH_URL_SSO = (
        'https://byx-sso-api-prd.azurewebsites.net/api/autenticacao/Login'
    )
    # CONST_AUTH_URL_SSO = "https://byx-sso-api-hml.azurewebsites.net/api/autenticacao/Login"

    payload = json.dumps({
        'Usuario': settings.USUARIO_API_SSO,
        'Senha': settings.PASSWORD_API_SSO,
    })
    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.request(
        'POST', CONST_AUTH_URL_SSO, headers=headers, data=payload
    )
    response_obj = json.loads(response.text)
    return response_obj['token']


def insere_proposta_inss_financeira_hub(
    contrato, tx_mes_contrato, nm_base_jurus, tx_multa_contrato
):
    """Realiza a inclusão de uma nova proposta na financeira Qi Tech e inclui a CCB retornada por eles nos anexos do contrato no nosso banco de dados"""

    CONST_HUB_FINANCEIRA_QITECH_URL = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )

    authorization = autenticacao_hub()

    contrato_margem_livre = MargemLivre.objects.filter(contrato=contrato).last()
    in100 = DadosIn100.objects.filter(numero_beneficio=contrato.numero_beneficio).last()

    dados_bancarios_cliente = DadosBancarios.objects.filter(
        cliente=contrato.cliente
    ).last()

    # DADOS REFERENTE AO CLIENTE
    nm_cliente = contrato.cliente.nome_cliente or ''
    nm_sexo = contrato.cliente.sexo or ''
    nm_estado_civil = contrato.cliente.estado_civil or ''
    nu_rg = contrato.cliente.documento_numero or ''

    dt_emissao_rg = str(contrato.cliente.documento_data_emissao) or ''
    nu_ddd_telefone_celular = contrato.cliente.telefone_celular or ''
    nm_rua = contrato.cliente.endereco_logradouro or ''
    nm_sigla_estado = contrato.cliente.endereco_uf or ''
    nm_cidade = contrato.cliente.endereco_cidade or ''
    nm_bairro = contrato.cliente.endereco_bairro or ''
    nu_endereco = contrato.cliente.endereco_numero or ''
    cep = contrato.cliente.endereco_cep or ''
    nm_complemento = contrato.cliente.endereco_complemento or ''
    dt_nascimento = str(contrato.cliente.dt_nascimento) or ''
    nm_mae = contrato.cliente.nome_mae or ''
    nu_cpf = contrato.cliente.nu_cpf or ''

    # uf_beneficio = contrato.cliente.ufBeneficio
    # nu_beneficio = ''
    nu_beneficio = int(in100.numero_beneficio) or ''
    uf_beneficio = contrato.cliente.endereco_uf or ''
    cd_banco = dados_bancarios_cliente.conta_banco or ''
    nu_conta = dados_bancarios_cliente.conta_numero or ''
    nu_conta_digito = dados_bancarios_cliente.conta_digito or ''
    nu_agencia = dados_bancarios_cliente.conta_agencia or ''
    tipo_conta = dados_bancarios_cliente.conta_tipo or ''

    # DADOS REFERENTE AO CONTRATO
    dt_primeiro_vencimento = (
        str(contrato_margem_livre.dt_vencimento_primeira_parcela) or ''
    )

    qt_parcelas = contrato_margem_livre.qtd_parcelas or ''
    tx_efetiva_mes = contrato.taxa_efetiva_mes / 100 or ''

    nu_contrato_financeira = 'BYX' + str(contrato.id).rjust(10, '0')
    vr_parcela = contrato_margem_livre.vr_parcelas or ''

    nu_ddd_telefone, nu_telefone = separar_numero_ddd(str(nu_ddd_telefone_celular))

    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }

    dt_desembolso_formatada = str(datetime.now().date())

    payload = {
        'NmEndpoint': 'debt',
        'NmVerb': 'POST',
        'JsonBody': {
            'borrower': {
                'is_pep': False,
                'name': nm_cliente,
                'gender': traduzir_sexo(nm_sexo),
                'marital_status': traduzir_estado_civil(nm_estado_civil),
                'document_identification_number': nu_rg,
                'document_identification_type': 'rg',
                'document_identification_date': dt_emissao_rg,
                'phone': {
                    'country_code': '055',
                    'area_code': nu_ddd_telefone,
                    'number': nu_telefone,
                },
                'address': {
                    'street': nm_rua,
                    'state': nm_sigla_estado,
                    'city': nm_cidade,
                    'neighborhood': nm_bairro,
                    'number': str(nu_endereco),
                    'postal_code': cep,
                    'complement': nm_complemento,
                },
                'role_type': 'issuer',
                'birth_date': dt_nascimento,
                'mother_name': nm_mae,
                'person_type': 'natural',
                'nationality': 'Brasileiro',
                'individual_document_number': formatar_cpf(nu_cpf),
            },
            'financial': {
                'first_due_date': dt_primeiro_vencimento,
                'installment_face_value': float(vr_parcela),
                'disbursement_date': dt_desembolso_formatada,
                'limit_days_to_disburse': 7,
                'number_of_installments': int(qt_parcelas),
                'interest_type': 'pre_price_days',
                'monthly_interest_rate': float(tx_efetiva_mes),
                'fine_configuration': {
                    'monthly_rate': tx_mes_contrato,
                    'interest_base': nm_base_jurus,
                    'contract_fine_rate': tx_multa_contrato,
                },
                'credit_operation_type': 'ccb',
                'interest_grace_period': 0,
                'principal_grace_period': 0,
            },
            'simplified': True,
            'collaterals': [
                {
                    'percentage': 1,
                    'collateral_data': {
                        'benefit_number': nu_beneficio,
                        'state': uf_beneficio,
                    },
                    'collateral_type': 'social_security',
                }
            ],
            'disbursement_bank_account': {
                'name': nm_cliente,
                'bank_code': cd_banco,
                'account_type': traduzir_tipo_conta(tipo_conta),
                'branch_number': str(nu_agencia),
                'account_number': str(nu_conta),
                'account_digit': str(nu_conta_digito),
                'document_number': formatar_cpf(nu_cpf),
                'transfer_method': 'pix',
            },
            'purchaser_document_number': settings.CONST_CNPJ_CESSIONARIO,
            'additional_data': {
                'contract': {'contract_number': nu_contrato_financeira}
            },
        },
    }

    # anexo_contrato = AnexoContrato.objects.create(contrato=contrato)

    response = requests.request(
        'POST',
        CONST_HUB_FINANCEIRA_QITECH_URL,
        headers=headers,
        data=json.dumps(payload),
    )

    # Imprime o status da resposta, o JSON da resposta e os detalhes de erro, se houver
    # print(f"Status da resposta: {response.status_code}")
    # print(f"JSON da resposta: {response.text}")

    if response.status_code in {200, 201, 202}:
        insere_proposta_inss_financeira_obj_response = json.loads(response.text)
        json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)
        print(json_obj_response)
        try:
            contrato_margem_livre.document_key_QiTech_CCB = json_obj_response['data'][
                'contract'
            ]['urls']
            contrato_margem_livre.related_party_key = json_obj_response['data'][
                'borrower'
            ]['related_party_key']
            created_at_str = json_obj_response['data']['collaterals'][0]['created_at']
            contrato_margem_livre.dt_envio_proposta_CIP = datetime.strptime(
                created_at_str, '%Y-%m-%dT%H:%M:%S.%f'
            ).date()
            contrato_margem_livre.collateral_key = json_obj_response['data'][
                'collaterals'
            ][0]['collateral_key']
            contrato_margem_livre.sucesso_insercao_proposta = True
            contrato_margem_livre.save()
        except Exception as e:
            print('Erro:', e)
    else:
        insere_proposta_inss_financeira_obj_response = json.loads(response.text)
        json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)
        print(json_obj_response)
        try:
            contrato_margem_livre.sucesso_insercao_proposta = False
            # contrato_margem_livre.insercao_sem_sucesso = json_obj_response['data']['title']
            contrato_margem_livre.save()
            data_atual = timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')
            LogWebhook.objects.create(
                chamada_webhook=f'WEBHOOK QITECH ERRO - INSERÇÃO DA PROPOSTA {data_atual}',
                log_webhook=json_obj_response,
            )
            logger.error(
                f'{contrato.cliente.id_unico} - Ocorreu um erro ao tentar inserir a Proposta\n Payload {payload}',
                exc_info=True,
            )
        except Exception as e:
            print('Erro:', e)
        raise Exception('Ocorreu um erro ao tentar Inserir a Proposta.')
