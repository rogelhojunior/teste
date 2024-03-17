import uuid

from django.db import models


class SetUpModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    created_at = models.DateTimeField(
        verbose_name='Criado em',
        auto_now_add=True,
        blank=True,
    )
    updated_at = models.DateTimeField(
        verbose_name='Atualizado em',
        auto_now=True,
        blank=True,
    )

    class Meta:
        abstract = True
