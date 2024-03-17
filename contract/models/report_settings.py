from django.db import models


class ReportSettings(models.Model):
    subject = models.CharField(verbose_name='Assunto do email', max_length=300)
    msg_email = models.CharField(
        verbose_name='Mensagem Email', max_length=300, null=True, blank=True
    )

    def __str__(self):
        return self.subject

    class Meta:
        verbose_name = '3. Configurações Relatorios'
        verbose_name_plural = '3. Configurações Relatorios'
