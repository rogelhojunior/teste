from django.db import models

from utils.models import SetUpModel


class BackofficeConfigs(SetUpModel):
    session_expiration_time = models.PositiveIntegerField(
        verbose_name='Tempo de expiração da sessão no backoffice',
        help_text='Tempo em minutos',
        null=True,
        blank=True,
        default=1440,  # 24 Horas
        unique=True,
    )

    email_password_expiration_days = models.PositiveIntegerField(
        verbose_name='Prazo de expiração do link de redefinição de senha',
        help_text='Prazo em dias úteis',
        default=5,  # Valor padrão de 5 dias úteis
    )

    subsequent_password_expiration_days = models.PositiveIntegerField(
        verbose_name='Prazo de expiração das senhas subsequentes',
        help_text='Prazo em dias corridos',
        default=30,  # Valor padrão de 30 dias
    )

    def __str__(self):
        return 'Configuração do backoffice'

    class Meta:
        verbose_name = '7. Configuração do backoffice'
        verbose_name_plural = '7. Configurações do backoffice'
