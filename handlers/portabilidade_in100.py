import json
import logging
import re
import uuid
from datetime import datetime

import requests
from django.conf import settings

from api_log.models import LogCliente, LogWebhook, QitechRetornos
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.models.anexo_cliente import AnexoCliente
from handlers.consultas import url_to_base64
from handlers.insere_proposta_inss_financeira import autenticacao_hub
from handlers.webhook_qitech import envio_termo_in100

logger = logging.getLogger('digitacao')


def formatar_cpf(cpf):
    return cpf.replace('.', '').replace('-', '')


def consulta_beneficio_in100_portabilidade(cliente, numero_beneficio, dados_in100):
    """Chama a IN100 para consultar renda líquida na etapa de simulação"""

    CONST_HUB_FINANCEIRA_QITECH_URL = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )
    anexo = AnexoCliente.objects.filter(cliente=cliente).first()
    documento_base_64 = url_to_base64(anexo.anexo_url)
    resposta = envio_termo_in100(
        anexo.nome_anexo,
        anexo.anexo_url,
        anexo.anexo_extensao,
        documento_base_64,
        anexo,
        cliente,
    )

    if not resposta['retornado']:
        dados_in100.sucesso_envio_termo_in100 = False
        dados_in100.envio_termo_sem_sucesso = resposta['motivo']
        dados_in100.save()
        return False
    authorization = autenticacao_hub()
    dados_in100.sucesso_envio_termo_in100 = True
    dados_in100.envio_termo_sem_sucesso = '-'
    dados_in100.save()
    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }

    session_id = str(uuid.uuid4())
    telefone = cliente.telefone_celular
    numero_telefone = re.sub(r'\D', '', telefone)
    area_code = numero_telefone[:2]
    numero = numero_telefone[2:]
    payload = {
        'NmEndpoint': 'social_security/balance_request',
        'NmVerb': 'POST',
        'JsonBody': {
            'document_number': f'{formatar_cpf(cliente.nu_cpf)}',
            'benefit_number': int(numero_beneficio),
            'authorization_term': {
                'document_number': f'{formatar_cpf(cliente.nu_cpf)}',
                'signature': {
                    'signer': {
                        'name': f'{cliente.nome_cliente}',
                        'email': f'{cliente.email}',
                        'phone': {
                            'number': str(numero),
                            'area_code': str(area_code),
                            'country_code': '55',
                        },
                        'document_number': f'{formatar_cpf(cliente.nu_cpf)}',
                    },
                    'authentication_type': 'opt_in',
                    'authenticity': {
                        'timestamp': f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}",
                        'ip_address': f'{cliente.IP_Cliente}',
                        'fingerprint': {},
                        'third_party_additional_data': {},
                        'session_id': session_id,
                    },
                    'signed_object': {'document_key': f"{resposta['document_key']}"},
                },
            },
        },
    }
    response = requests.request(
        'POST',
        CONST_HUB_FINANCEIRA_QITECH_URL,
        headers=headers,
        data=json.dumps(payload),
    )
    resposta = {}
    dados_in100 = DadosIn100.objects.filter(numero_beneficio=numero_beneficio).first()
    if response.status_code in {200, 201, 202}:
        retorno_in100 = json.loads(response.text)
        json_obj_response = json.loads(retorno_in100)
        dados_in100.sucesso_chamada_in100 = True
        dados_in100.balance_request_key = json_obj_response['balance_request_key']
        dados_in100.save()
        resposta['response'] = json_obj_response
        resposta['retornado'] = True
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            retorno=retorno_in100,
            tipo='in100-originacao',
        )
        logger.info(
            f'{cliente.id_unico} : Autorização IN100 enviada para QITECH.\n Payload {payload}'
        )
    else:
        json_obj_response = response.json()
        dados_in100.sucesso_chamada_in100 = False
        dados_in100.chamada_sem_sucesso = f'{json_obj_response}'
        dados_in100.save()
        resposta['response'] = json_obj_response
        resposta['retornado'] = False
        # A data e a hora atuais
        agora = datetime.now()
        # Formatar a data e a hora
        formatado = agora.strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'WEBHOOK QITECH ERRO - CONSULTA BENEFICIO {formatado}',
            log_webhook=json_obj_response,
        )
        logger.error(
            f'{cliente.id_unico} - Erro ao consultar benefício IN100', exc_info=True
        )
    return resposta
