import logging

import requests
from django.conf import settings


def publish(message):
    try:
        response = requests.post(settings.FACE_MATCH_API_ENDPOINT, json=message)
        response.raise_for_status()  # this will raise an exception for 4xx and 5xx status codes
        return response
    except Exception as e:
        logging.error(f'Error publishing message: {e}')
        raise


class SendFaceMatchingRequest:
    def __call__(self, message):
        logging.info('Sending SendFaceMatchingRequest to queue...')
        return publish(message)
