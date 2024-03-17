import logging

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from custom_auth.models import UserProfile
from message_bus.web_socket_message import send_to_web_socket_server

logger = logging.getLogger('digitacao')


def handle_face_match_response(message):
    try:
        user_uuid = message['user_uuid']
        match_result = message['result']
        error = message['error']

        usuario = UserProfile.objects.get(unique_id=user_uuid)
        usuario.is_checked = match_result

        usuario.last_checked = (
            timezone.now()
        )  # isso irá gerar um objeto datetime que é "consciente" do fuso horário

        usuario.save()

        _send_matching_result_to_user(user_uuid, match_result, error)

        return match_result

    except KeyError as e:
        print(f'Error extracting key from message: {str(e)}')

    except ObjectDoesNotExist:
        print(f'User profile not found for UUID: {user_uuid}')

    except Exception as e:
        print(f'An error occurred: {str(e)}')


def _send_matching_result_to_user(user_uuid, result, error=None):
    print('face match sended to user !')
    return send_to_web_socket_server(
        socket_id=user_uuid,
        data={'user_id': user_uuid, 'has_matched': result, 'error': error},
    )
