import json

import newrelic.agent
import requests
from django.conf import settings


def autenticacao_hub_inss():
    try:
        url = f'{settings.SSO_API_URL}/autenticacao/Login'

        # TODO: ARMAZENAMENTO DE VARIÁVEIS NO GITHUB
        payload = json.dumps({
            'Usuario': f'{settings.USUARIO_API_SSO}',
            'Senha': f'{settings.PASSWORD_API_SSO}',
        })
        headers = {
            'Content-Type': 'application/json',
        }

        response = requests.request('POST', url, headers=headers, data=payload)
        response_obj = json.loads(response.text)
        authorization = response_obj['token']
    except Exception:
        newrelic.agent.notice_error()
        authorization = None
    return authorization
