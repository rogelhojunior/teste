from django.db import models


class Data(models.Model):
    dt_data = models.DateField(verbose_name='Data')
    base = models.IntegerField(verbose_name='')
    ds_mes = models.CharField(max_length=50, null=True, verbose_name='Mês')
    ds_dia_da_semana = models.CharField(
        max_length=50, null=True, verbose_name='Dia da Semana'
    )
    ds_feriado = models.CharField(
        max_length=50, null=True, verbose_name='Descrição do Feriado'
    )
    fl_final_de_semana = models.BooleanField(verbose_name='Final de Semana')
    fl_feriado = models.BooleanField(verbose_name='Feriado')
    fl_ponto_facultativo = models.BooleanField(verbose_name='Ponto Facultativo')
    fl_dia_util = models.BooleanField(verbose_name='Dia Útil')
    dt_data_util = models.DateField(verbose_name='Data Útil')

    def __str__(self):
        return f'{self.dt_data} - {self.ds_feriado}'

    class Meta:
        verbose_name = 'Datas e Feriados'
        verbose_name_plural = '2. Datas e Feriados'
