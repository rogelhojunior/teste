from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from custom_auth.models import UserSession


@receiver(post_save, sender=User)
def create_user_session(sender, instance, created, **kwargs):
    if created:
        UserSession.objects.create(user=instance)


@receiver(post_delete, sender=User)
def delete_user_session(sender, instance, **kwargs):
    UserSession.objects.filter(user=instance).delete()
