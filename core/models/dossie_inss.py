from django.db import models


class DossieINSS(models.Model):
    cpf = models.CharField(max_length=14, verbose_name='CPF')
    matricula = models.CharField(max_length=20, verbose_name='Matrícula')
    data_envio = models.DateTimeField(verbose_name='Data do Envio')
    contrato = models.ForeignKey(
        'contract.Contrato',
        on_delete=models.CASCADE,
        verbose_name='Número do Contrato',
    )
    codigo_retorno = models.CharField(
        max_length=10, verbose_name='Código de Retorno', null=False, blank=False
    )
    hash_operacao = models.CharField(max_length=64, verbose_name='Hash da Operação')
    detalhe_erro = models.TextField(
        verbose_name='Detalhe do Erro', null=True, blank=True
    )

    def __str__(self):
        return f'Dossiê INSS - Contrato {self.contrato}'

    class Meta:
        verbose_name = 'Dossiê INSS'
        verbose_name_plural = '8. Dossiês INSS'
