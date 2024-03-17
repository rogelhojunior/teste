from logging import getLogger
from urllib.error import HTTPError

import requests
from django.conf import settings
from requests import ConnectionError, RequestException, Timeout

logger = getLogger(__name__)


def send_to_web_socket_server(socket_id, data):
    headers: dict[str, any] = {'Authorization': settings.WSS_AUTH_UUID}
    endpoint: str = f'{settings.URL_PUBLISH_WEBSOCKETS}?id={socket_id}'
    try:
        response = requests.post(url=endpoint, headers=headers, json=data)
        response.raise_for_status()
    except (HTTPError, ConnectionError, Timeout, RequestException) as err:
        logger.exception(
            msg=f'Error occurred in call {endpoint}: {err}',
            extra={
                'endpoint': endpoint,
                'headers': headers,
                'data': data,
                'status_code': response.status_code
                if isinstance(err, HTTPError)
                else None,
                'error_type': type(err).__name__,
            },
        )
        raise
    except Exception as err:
        logger.exception(
            msg='Something worng in IQ Request',
            extra={
                'endpoint': endpoint,
                'headers': headers,
                'data': data,
                'error_type': type(err).__name__,
            },
        )
        raise
    return response
