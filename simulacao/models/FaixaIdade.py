from django.db import models


class FaixaIdade(models.Model):
    nu_idade_minima = models.FloatField(verbose_name='Idade Mínima', null=True)
    nu_idade_maxima = models.FloatField(verbose_name='Idade Máxima', null=True)
    vr_minimo = models.FloatField(verbose_name='Valor Mínimo', null=True)
    vr_maximo = models.FloatField(verbose_name='Valor Máximo', null=True)
    nu_prazo_minimo = models.IntegerField(verbose_name='Prazo Mínimo', null=True)
    nu_prazo_maximo = models.IntegerField(verbose_name='Prazo Máximo', null=True)
    fl_possui_representante_legal = models.BooleanField(
        verbose_name='Possui Representante Legal', null=True
    )

    def __str__(self):
        return f'{self.nu_idade_minima} - {self.nu_idade_maxima}'

    class Meta:
        verbose_name = 'Faixa de Idade'
        verbose_name_plural = '1. Faixas de Idade'
