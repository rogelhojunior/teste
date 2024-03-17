from django.db import models

from contract.models.contratos import Contrato
from handlers.aws_boto3 import Boto3Manager


class AnexoAntifraude(models.Model):
    contrato = models.ForeignKey(
        Contrato, verbose_name='Contrato', on_delete=models.CASCADE
    )
    nome_anexo = models.CharField(verbose_name='Nome do anexo', max_length=300)
    anexo_extensao = models.CharField(verbose_name='Código extensão', max_length=10)
    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    arquivo = models.FileField(
        verbose_name='Documento', null=True, blank=True, upload_to='cliente'
    )
    anexado_em = models.DateTimeField(
        verbose_name='Anexado em',
        auto_now_add=True,
    )

    def __str__(self):
        return self.nome_anexo

    @property
    def get_attachment_url(self) -> str:
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.anexo_url)

    class Meta:
        verbose_name = 'Contrato - Anexo Antifraude'
        verbose_name_plural = 'Contrato - Anexos Antifraude'
