import json
import logging
import uuid

import requests
from django.conf import settings
from core.utils import consulta_cliente

logger = logging.getLogger('digitacao')


def zenvia_sms_token():
    url = 'https://apicore.d1.cx/login/63c1d75ad5009e525fd3d831/token'

    payload = {
        'Clientid': settings.CLIENT_ID_ZENVIA,
        'Grand_type': 'client_credentials',
        'ClientSecret': settings.CLIENT_SECRET_ZENVIA,
        'Audience': 'https://apicore.d1.cx',
    }
    files = []
    headers = {'TenantId': '63c1d75ad5009e525fd3d831'}

    response = requests.request('POST', url, headers=headers, data=payload, files=files)
    return json.loads(response.text)


def zenvia_sms(numero_cpf, telefone, mensagem):
    try:
        if not numero_cpf or not telefone or not mensagem:
            logger.info('Error ao enviar parametros para a função')
            raise ValueError('CPF, telefone e mensagem são obrigatórios')

        token_zenvia = zenvia_sms_token()
        token_zenvia = token_zenvia.get('access_token')
        if not token_zenvia:
            raise Exception('Falha ao obter token de acesso')

        id = str(uuid.uuid4())

        url = settings.URL_ENVIO_ZENVIA
        cliente = consulta_cliente(numero_cpf)
        if not cliente:
            logger.info('Cliente não encontrado')
            raise ValueError('Cliente não encontrado')

        journey_id = settings.JOURNEY_ID_ZENVIA
        customer_id = cliente.id_unico
        customer_name = cliente.nome_cliente
        phone_number = f'+55{telefone}'
        phone_kind = 'cellphone'
        var_mensagem = mensagem
        correlation_id = id

        payload = {
            'journeyId': journey_id,
            'customer': {
                'id': str(customer_id),
                'name': customer_name,
                'phones': [{'number': phone_number, 'kind': phone_kind}],
            },
            'Variables': {'var_mensagem': var_mensagem},
            'correlationId': correlation_id,
        }

        headers = {
            'TenantId': '63c1d75ad5009e525fd3d831',
            'Authorization': f'Bearer {token_zenvia}',
            'Content-Type': 'application/json',
        }

        response = requests.post(url, headers=headers, json=payload)
        logger.info(f'SMS enviado com status {response.status_code}: {response.json()}')
        if response.status_code != 200:
            response.raise_for_status()

    except Exception as e:
        logger.info(f'Erro ao enviar SMS: {e}')
        raise
