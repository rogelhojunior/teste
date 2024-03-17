from django.db import models

from contract.choices import TIPOS_CONTRATO


class ComissaoTaxa(models.Model):
    cd_contrato_tipo = models.SmallIntegerField(
        choices=TIPOS_CONTRATO,
        db_index=True,
        verbose_name='Contrato Tipo',
    )
    cd_convenio = models.IntegerField(null=True, verbose_name='Código Convenio')
    prazo = models.IntegerField(null=True, verbose_name='Prazo')
    tx_efetiva_contrato_min = models.FloatField(
        null=True, verbose_name='Taxa Efetiva Contrato Min'
    )
    tx_efetiva_contrato_max = models.FloatField(
        null=True, verbose_name='Taxa Efetiva Contrato Max'
    )
    tx_comissao_total = models.FloatField(null=True, verbose_name='Taxa Comissao Total')
    tx_comissao_flat = models.FloatField(null=True, verbose_name='Taxa Comissao Flat')
    tx_comissao_pmt = models.FloatField(null=True, verbose_name='Taxa Comissao Pmt')
    tx_parcelada_vf = models.FloatField(null=True, verbose_name='Taxa Parcelada VF')
    tx_parcelada_vp = models.FloatField(null=True, verbose_name='Taxa Parcelada VP')
    tx_total_vp = models.FloatField(null=True, verbose_name='Taxa Total VP')
    tx_antecipacao = models.FloatField(null=True, verbose_name='Taxa Antecipacao')
    dt_vigencia_inicio = models.DateTimeField(
        null=True, verbose_name='Data Vigencia Inicio'
    )
    dt_vigencia_fim = models.DateTimeField(null=True, verbose_name='Data Vigencia Fim')
    dt_cadastro = models.DateTimeField(null=True, verbose_name='Data Cadastro')
    fl_ativa = models.BooleanField(null=True, verbose_name='Flag Ativa')

    def __str__(self):
        return 'Taxa de Comissão'

    class Meta:
        verbose_name = 'Taxa de Comissão'
        verbose_name_plural = '3. Taxas de Comissão'
