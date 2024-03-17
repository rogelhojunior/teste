import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from custom_auth.messages.emails import send_activation_email
from custom_auth.models import UserProfile
from custom_auth.utils import generate_simple_password

logger = logging.getLogger('Cadastro de Usuarios')


@receiver(post_save, sender=UserProfile)
def user_created(sender, instance, created, **kwargs):
    """
    Creates a secure password and sends it to the user's
    email after being created
    """

    if created:
        password = generate_simple_password()
        instance.set_password(password)
        instance.save()

        try:
            send_activation_email(instance, password)

        except Exception as exception:
            logger.error(
                f'Activation email from account {instance.email}  could not be sent. '
                f'Error: {str(exception)}',
                exc_info=True,
            )
    elif hasattr(instance, '_password_changed'):
        instance.password_changed_at = timezone.now()
        # Salvar a instância sem acionar o signal novamente
        UserProfile.objects.filter(pk=instance.pk).update(
            password_changed_at=instance.password_changed_at, is_checked=False
        )
