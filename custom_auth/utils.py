import base64
import os

from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core import settings
from custom_auth.custom_token_generator import custom_token_generator
from handlers.email import send_email


def generate_simple_password(length=8):
    """
    Create ascii based password with defined length for user's password

    Parameters:
        - length: length of the password to be generated. By default, the value is 8.

    Return:
        String with an alphanumeric password of the requested length. Ex: 6Amtry80.
    """

    return base64.b64encode(os.urandom(length)).decode('ascii')


def check_password_expiration(user, request):
    if user.is_password_expired():
        # Construir o link de redefinição de senha
        reset_link = get_reset_link(user)

        # Contexto para o template de e-mail
        context = {
            'reset_link': reset_link,
            'user': user,
            'email_logo': f'{settings.EMAIL_LOGO}',
        }

        # Enviar e-mail usando o método personalizado
        send_email(
            'emails/account/password_reset_email.html',
            'emails/account/password_reset_subject.txt',
            'Redefinição de Senha Solicitada',
            user.email,
            context,
        )

        return False  # Indica que a senha está expirada
    return True  # Senha válida


def get_reset_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = custom_token_generator.make_token(user)
    # Remove '/login' from the URL if it exists
    base_url = settings.FRONT_LOGIN
    if base_url.endswith('/login'):
        base_url = base_url.rsplit('/login', 1)[0]

    return f'{base_url}/reset-password/{uid}/{token}/'


def extract_last_part_of_url(url):
    # Divide a URL em partes usando '/' como delimitador
    parts = url.split('/')

    # Filtra os elementos vazios e pega os dois últimos elementos não vazios
    parts = list(filter(None, parts))
    if len(parts) >= 2:
        return f'{parts[-2]}/{parts[-1]}'
    else:
        return parts[-1] if parts else ''
