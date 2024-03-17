from django.db import models

from contract.choices import SEGURADORAS, TIPOS_COMUNICACAO


class Seguradoras(models.Model):
    nome = models.SmallIntegerField(
        verbose_name='Nome',
        choices=SEGURADORAS,
        blank=True,
        null=True,
    )
    tipo_comunicacao = models.SmallIntegerField(
        verbose_name='Tipo de Comunicação',
        choices=TIPOS_COMUNICACAO,
        blank=True,
        null=True,
    )
    url_arquvio = models.CharField(
        verbose_name='URL Arquivo', max_length=300, null=True, blank=True
    )
    url_api = models.CharField(
        verbose_name='URL API', max_length=300, null=True, blank=True
    )
    usuario_seguro = models.CharField(
        verbose_name='Usuário', max_length=300, null=True, blank=True
    )
    senha_seguro = models.CharField(
        verbose_name='Senha', max_length=300, null=True, blank=True
    )

    def get_nome_display(self):
        return dict(SEGURADORAS).get(self.nome)

    def __str__(self):
        return self.get_nome_display() or ''

    class Meta:
        verbose_name = 'Parametro Seguradora'
        verbose_name_plural = '3. Parametros Seguradoras'
