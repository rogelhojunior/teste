import logging
import smtplib
import ssl
import threading

from django.conf import settings
from django.core.mail import send_mail as mail
from django.template.loader import render_to_string

# TODO: Credenciais não podem estar no mesmo banco de dados da aplicação -> exigência dock
habilitarssl = settings.EMAIL_HABILITAR_SSL
host = settings.EMAIL_HOST
porta = settings.EMAIL_PORT
remetente = settings.EMAIL_REMETENTE
usuario = settings.EMAIL_USUARIO
senha = settings.EMAIL_SENHA
emailTi = settings.EMAIL_TI

logger = logging.getLogger('Envio de Emails')


def send_email(template, plain_text, subject, email, context):
    """
    Send async email with html template. Main method for sending email.
    This method use configured email properties on local_settings
    """

    msg_html = render_to_string(template, context)

    # msg_plain is used if the recipient's email does not
    # have resources to render the html version
    msg_plain = render_to_string(plain_text, context)

    threading.Thread(
        target=mail,
        kwargs={
            'subject': subject,
            'message': msg_plain,
            'from_email': settings.EMAIL_HOST_USER,
            'recipient_list': [email],
            'html_message': msg_html,
        },
    ).start()


def enviar_email(message):
    """
    Deprecated Method for send emails and will be replace for send_email function.
    """

    if not settings.EMAIL_HABILITA_EMAIL:
        return

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, porta) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(remetente, senha)
            server.sendmail(remetente, emailTi, message)

    except Exception as exception:
        logger.error(f'Email could not be sent. Error: {str(exception)}', exc_info=True)
