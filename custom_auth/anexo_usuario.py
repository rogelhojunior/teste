from django.db import models

from contract.choices import TIPOS_ANEXO
from custom_auth.models import UserProfile
from handlers.aws_boto3 import Boto3Manager


class AnexoUsuario(models.Model):
    usuario = models.ForeignKey(
        UserProfile, verbose_name='Usuário', on_delete=models.CASCADE
    )

    tipo_anexo = models.SmallIntegerField(
        verbose_name='Tipo do anexo', choices=TIPOS_ANEXO, null=True, blank=True
    )
    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    selfie_url = models.URLField(
        verbose_name='URL da selfie', max_length=500, null=True, blank=True
    )
    arquivo = models.FileField(
        verbose_name='Documento', null=True, blank=True, upload_to='cliente'
    )
    anexado_em = models.DateTimeField(verbose_name='Anexado em', auto_now_add=True)

    def __str__(self):
        return self.usuario.identifier

    @property
    def get_attachment_url(self) -> str:
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.anexo_url)

    @property
    def get_selfie_url(self) -> str:
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.selfie_url)

    class Meta:
        verbose_name = 'Usuário - Anexo'
        verbose_name_plural = 'Usuário - Anexos'
