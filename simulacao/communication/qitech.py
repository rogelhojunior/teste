import locale
import logging
from datetime import datetime
from hashlib import md5

import requests
from django.conf import settings
from jose import jwt

logger = logging.getLogger('digitacao')


class QitechApiIntegration:
    def execute(self, base_url, endpoint, body, verb):
        try:
            headers = {'alg': 'ES512', 'typ': 'JWT'}

            api_key = settings.QITECH_INTEGRATION_KEY
            client_private_key = settings.QITECH_CLIENT_PRIVATE_KEY

            encoded_body_token = jwt.encode(
                claims=body, key=client_private_key, algorithm='ES512'
            )
            request_body = {'encoded_body': encoded_body_token}

            md5_encode = md5()
            md5_encode.update(encoded_body_token.encode())
            md5_body = md5_encode.hexdigest()

            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            date = datetime.utcnow().strftime(settings.QITECH_DATE_FORMAT)

            method = verb
            content_type = 'application/json'
            string_to_sign = (
                method
                + '\n'
                + md5_body
                + '\n'
                + content_type
                + '\n'
                + date
                + '\n'
                + endpoint
            )

            claims = {'sub': api_key, 'signature': string_to_sign}
            encoded_header_token = jwt.encode(
                claims=claims,
                key=client_private_key,
                algorithm='ES512',
                headers=headers,
            )

            authorization = 'QIT' + ' ' + api_key + ':' + encoded_header_token
            request_header = {'AUTHORIZATION': authorization, 'API-CLIENT-KEY': api_key}

            url = f'{base_url}{endpoint}'

            resp = requests.post(url=url, headers=request_header, json=request_body)

            value = resp.json()['encoded_body']
            status_code = resp.status_code
            json = jwt.decode(value, key=None, options={'verify_signature': False})
            return json, status_code

        except Exception as e:
            logger.error(f'Erro ao executar integration API QITech (execute): {e}')
            raise
