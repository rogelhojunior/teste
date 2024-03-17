import requests
from django.conf import settings


def gerar_token_dock(client_id, client_password):
    # Obtem o token de acesso para as demais APIs
    url_token = settings.DOCK_URL_TOKEN

    url = f'{url_token}/oauth2/token'
    querystring = {'grant_type': 'client_credentials'}

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.request(
        'POST',
        url,
        headers=headers,
        params=querystring,
        auth=(client_id, client_password),
    )
    return response.text
