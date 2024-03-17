from django.conf import settings

from handlers.email import send_email


def send_activation_email(user, password):
    """Custom email for new user's activation account using"""

    login_url = f'{settings.BASE_URL}/admin/login/?next=/admin/'
    if not user.is_staff:
        login_url = f'{settings.FRONT_LOGIN}'
    context = {
        'name': user.name.split(' ')[0],
        'email': user.email,
        'login': user.identifier,
        'password': password,
        'login_url': login_url,
        'reset_url': f'{settings.BASE_URL}/accounts/password_reset/',
        'support_email': settings.SUPPORT_EMAIL,
        'email_logo': f'{settings.EMAIL_LOGO}',
    }

    template = 'emails/account/activation.html'
    plaintext = 'emails/account/activation.txt'
    subject = 'Cadastro realizado com Sucesso!'
    send_email(template, plaintext, subject, user.email, context)
