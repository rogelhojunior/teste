from django.db import models

from core.models import Cliente
from handlers.aws_boto3 import Boto3Manager


class AnexoCliente(models.Model):
    cliente = models.ForeignKey(
        Cliente, verbose_name='Cliente', on_delete=models.CASCADE
    )
    nome_anexo = models.CharField(verbose_name='Nome do anexo', max_length=300)
    anexo_extensao = models.CharField(verbose_name='Código extensão', max_length=10)
    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    anexado_em = models.DateTimeField(verbose_name='Anexado em', auto_now_add=True)

    def __str__(self):
        return self.nome_anexo

    @property
    def get_attachment_url(self) -> str:
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.anexo_url)

    class Meta:
        verbose_name = 'Cliente - Anexo'
        verbose_name_plural = 'Cliente - Anexos'
