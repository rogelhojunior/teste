import requests
from celery.utils.log import get_task_logger

logger = get_task_logger('insurance')


def publish_async(url, message, headers=None):
    headers = headers or {}
    try:
        response = requests.post(url, json=message, headers=headers)
        response.raise_for_status()
        return response

    except (
        requests.HTTPError,
        ConnectionError,
        requests.Timeout,
        requests.RequestException,
    ) as err:
        logger.exception(
            msg=f'Error occurred in call {url}: {err}',
            extra={
                'endpoint': url,
                'status_code': response.status_code
                if isinstance(err, requests.HTTPError)
                else None,
                'error_type': type(err).__name__,
            },
        )
        raise
    except Exception as e:
        logger.exception(f'Something wrong with request to Insurance Api: {e}')
        raise
