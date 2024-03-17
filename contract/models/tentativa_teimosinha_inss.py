from django.db import models

from contract.models.contratos import Contrato


class TentativaTeimosinhaINSS(models.Model):
    contrato = models.ForeignKey(
        Contrato, verbose_name='Contrato', on_delete=models.CASCADE
    )
    solicitada_em = models.DateTimeField(
        verbose_name='Solicitada em',
    )
    respondida_em = models.DateTimeField(
        verbose_name='Respondida em',
        null=True,
        blank=True,
    )
    proxima_tentativa_em = models.DateTimeField(
        verbose_name='Próxima tentativa em',
        null=True,
        blank=True,
    )
    sucesso = models.BooleanField(
        verbose_name='Sucesso',
        default=False,
    )
    retorno_dataprev = models.JSONField(
        verbose_name='Retorno Dataprev',
        null=True,
        blank=True,
    )

    def __str__(self):
        return f'Tentativa Teimosinha INSS - Contrato {self.contrato.id}'
