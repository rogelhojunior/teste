from django.db import models

from contract.models.contratos import Contrato


class ValidacaoContrato(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_validacoes',
    )

    mensagem_observacao = models.CharField(
        verbose_name='Mensagem de Observação', max_length=300, null=True, blank=True
    )
    checked = models.BooleanField(
        verbose_name='Status',
        default=True,
    )
    data_criacao = models.DateTimeField(
        verbose_name='Inserido em', auto_now_add=True, null=True, blank=True
    )
    retorno_hub = models.TextField(
        verbose_name='Código extensão', default='', null=True, blank=True
    )
