"""
This module implements utils functions to handle Qi Tech API.
"""

import json
import locale

# built-in
from datetime import datetime

import jwt
import requests

# third
from rest_framework.response import Response

# local
from core import settings


def decrypt(text: str):
    """
    Decrypt some text content using jwt.
    """
    return jwt.decode(text, options={'verify_signature': False})


def build_qi_tech_auth_header(endpoint: str) -> dict:
    """
    Build complex Qi Tech authorization header.
    """
    api_key = settings.QITECH_INTEGRATION_KEY
    client_private_key = settings.QITECH_CLIENT_PRIVATE_KEY

    md5_body = ''  # Para requisições GET, o corpo pode ser vazio
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    date = datetime.utcnow().strftime(settings.QITECH_DATE_FORMAT)

    method = 'GET'
    content_type = 'application/json'
    string_to_sign = (
        method + '\n' + md5_body + '\n' + content_type + '\n' + date + '\n' + endpoint
    )

    claims = {'sub': api_key, 'signature': string_to_sign}

    headers = {'alg': 'ES512', 'typ': 'JWT'}
    encoded_header_token = jwt.encode(
        payload=claims,
        key=client_private_key,
        algorithm='ES512',
        headers=headers,
    )

    authorization = 'QIT' + ' ' + api_key + ':' + encoded_header_token
    return {'AUTHORIZATION': authorization, 'API-CLIENT-KEY': api_key}


def send_get_to_qi_tech(endpoint: str) -> Response:
    """
    Send a GET request to Qi Tech API on the specified endpoint.
    """
    request_header = build_qi_tech_auth_header(endpoint)

    base_url = settings.QITECH_BASE_ENDPOINT_URL
    url = f'{base_url}{endpoint}'

    return requests.get(url=url, headers=request_header)


def extract_decoded_content(response: Response) -> str:
    """
    Decode the Qi Tech response content.
    """
    encoded_content = response.text
    encoded_body = json.loads(encoded_content)['encoded_body']
    return decrypt(encoded_body)
