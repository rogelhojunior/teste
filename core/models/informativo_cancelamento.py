from django.db import models

from contract.choices import TIPOS_CANCELMENTO
from contract.models.contratos import Contrato

# from core.models import Cliente


class InformativoCancelamentoPlano(models.Model):
    data_canelamento = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    motivo = models.SmallIntegerField(
        verbose_name='Motivo do cancelamento', choices=TIPOS_CANCELMENTO, default=1
    )
    valor_estorno = models.DecimalField(
        verbose_name='Valor do estorno',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        default=0,
    )
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_cancelamento',
    )
    cliente = models.ForeignKey(
        'core.Cliente',
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        related_name='cancelamento',
    )
