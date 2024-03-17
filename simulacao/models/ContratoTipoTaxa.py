from django.db import models

from contract.choices import TIPOS_CONTRATO


class ContratoTipoTaxa(models.Model):
    cd_contrato_tipo = models.SmallIntegerField(
        choices=TIPOS_CONTRATO,
        db_index=True,
        verbose_name='Contrato Tipo',
    )
    dt_inicio_vigencia = models.DateTimeField(
        null=True, verbose_name='Data Início Vigência'
    )
    dt_fim_vigencia = models.DateTimeField(null=True, verbose_name='Data Fim Vigência')
    vr_taxa_efetiva_mes_min = models.FloatField(
        null=True, verbose_name='Valor Taxa Efetiva Mês Min'
    )
    vr_taxa_efetiva_mes_max = models.FloatField(
        null=True, verbose_name='Valor Taxa Efetiva Mês Max'
    )

    def __str__(self):
        return 'Contrato Tipo Taxa'

    class Meta:
        verbose_name = 'Tipo Taxa'
