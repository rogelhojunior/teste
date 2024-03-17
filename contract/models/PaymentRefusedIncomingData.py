"""This module implements PaymentRefusedIncomingData model."""

from django.db import models


class PaymentRefusedIncomingData(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    transaction_key = models.CharField(
        verbose_name='Chave da transação',
        max_length=100,
        null=True,
        blank=True,
        help_text='Chave recebida da qi tech quando pagamento TED foi recusado.',
    )

    is_pix = models.BooleanField(
        verbose_name='É pix?',
        max_length=100,
        null=False,
        blank=False,
        default=False,
        help_text='Os dados são referentes à um erro no pix?',
    )

    is_ted = models.BooleanField(
        verbose_name='É ted?',
        max_length=100,
        null=False,
        blank=False,
        default=False,
        help_text='Os dados são referentes à um erro no ted?',
    )

    reason_id = models.CharField(
        verbose_name='Id da razão do cancelamento do pagamento',
        max_length=100,
        null=False,
        blank=False,
        help_text='Chave recebida da qi tech quando pagamento foi recusado.',
    )

    reason_description = models.CharField(
        verbose_name='Id da razão do cancelamento do pagamento',
        max_length=300,
        null=False,
        blank=False,
        help_text='Chave recebida da qi tech quando pagamento foi recusado.',
    )

    bank_data = models.ForeignKey(
        'core.DadosBancarios',
        verbose_name='bank_data',
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        default=None,
    )
