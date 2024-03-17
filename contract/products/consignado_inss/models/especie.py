from django.db import models

from contract.choices import TIPOS_PRODUTO


class EspecieIN100(models.Model):
    numero_especie = models.IntegerField(
        verbose_name='Número Espécie',
        null=True,
        blank=True,
    )
    nome_especie = models.CharField(
        verbose_name='Nome Especie', blank=False, null=False, max_length=255
    )
    tipo_produto = models.SmallIntegerField(
        verbose_name='Tipo Produto',
        choices=TIPOS_PRODUTO,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f'{self.numero_especie} - {self.nome_especie}'

    class Meta:
        verbose_name = 'Espécie IN100'
        verbose_name_plural = '1. Espécies IN100'
