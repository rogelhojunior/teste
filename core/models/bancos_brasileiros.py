from django.db import models

from custom_auth.models import Produtos


class BancosBrasileiros(models.Model):
    codigo = models.CharField(
        max_length=100, verbose_name='Codigo do banco', null=True, blank=False
    )
    nome = models.CharField(
        max_length=100, verbose_name='Nome do banco', null=True, blank=False
    )
    ispb = models.CharField(
        max_length=100, verbose_name='Código ISPB', null=True, blank=False
    )
    produto = models.ManyToManyField(
        Produtos,
        verbose_name='Produtos',
        related_name='bank_products',
        help_text='Selecione os produtos disponíveis para este banco',
        blank=True,
    )
    aceita_liberacao = models.BooleanField(
        default=False, verbose_name='Aceita liberação?'
    )

    def __str__(self):
        return self.codigo or ''

    @property
    def nome_(self):
        return f'{self.codigo} - {self.nome}'

    class Meta:
        verbose_name = '2. Banco brasileiro'
        verbose_name_plural = '2. Bancos brasileiros'
