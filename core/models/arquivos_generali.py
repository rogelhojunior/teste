from django.db import models


class ArquivoGenerali(models.Model):
    nmDocumento = models.CharField(verbose_name='Nome do documento', max_length=300)
    documento = models.FileField(
        verbose_name='Documento', null=True, blank=False, upload_to='arquivo'
    )
    sequencial = models.IntegerField(
        blank=True, null=True, verbose_name='Nº Seqüencial'
    )
    dtCriacao = models.DateTimeField(verbose_name='Data de criação', auto_now_add=True)
    criadoPor = models.ForeignKey(
        'custom_auth.UserProfile',
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.nmDocumento

    class Meta:
        verbose_name = 'Arquivo'
        verbose_name_plural = '3. Arquivos'
