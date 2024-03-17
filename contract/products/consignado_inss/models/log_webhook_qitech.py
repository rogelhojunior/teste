from django.db import models

from contract.models.contratos import Contrato


class LogWebHookQiTech(models.Model):
    contrato = models.ForeignKey(
        Contrato, verbose_name='Contrato', on_delete=models.CASCADE
    )

    nome_funcao_webhook = models.CharField(
        verbose_name='Nome da Função do Webhook', max_length=300, null=True, blank=True
    )
    json_entrada = models.TextField(verbose_name='Json Entrada', null=True, blank=True)
    json_saida = models.TextField(verbose_name='Json Saída', null=True, blank=True)
    dt_entrada = models.DateTimeField(
        verbose_name='Data de Entrada do Webhook', auto_now_add=True, null=True
    )
    dt_saida = models.DateTimeField(verbose_name='Data de Saída do Webhook', null=True)
    chave_retorno_financeira = models.CharField(
        verbose_name='Chave de Retorno da Financeira',
        max_length=300,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Log WebHook Qi Tech'
        verbose_name_plural = 'Logs WebHook Qi Tech'
