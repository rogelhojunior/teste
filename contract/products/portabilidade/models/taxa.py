from django.db import models

from contract.choices import TIPOS_PRODUTO
from contract.constants import EnumTipoProduto


class Taxa(models.Model):
    taxa = models.DecimalField(
        verbose_name='Taxa', decimal_places=2, max_digits=12, null=True, blank=True
    )
    tipo_produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.PORTABILIDADE,
    )
    ativo = models.BooleanField(verbose_name='Taxa ativa?', default=False)

    class Meta:
        verbose_name = 'Taxa'
        verbose_name_plural = 'Taxas'
