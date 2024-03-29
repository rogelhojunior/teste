# Generated by Django 4.2.2 on 2023-06-14 19:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_merge_20230613_1641'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='parametrosproduto',
            name='comprovante_residencia',
        ),
        migrations.RemoveField(
            model_name='parametrosproduto',
            name='documento_adicional',
        ),
        migrations.RemoveField(
            model_name='parametrosproduto',
            name='documento_pessoal',
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='cet_ano',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='CET ano'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='cet_mes',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='CET mês'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='idade_maxima',
            field=models.IntegerField(blank=True, null=True, verbose_name='Idade Máxima'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='idade_minima',
            field=models.IntegerField(blank=True, null=True, verbose_name='Idade Mínima'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='quantidade_maxima_parcelas',
            field=models.IntegerField(blank=True, null=True, verbose_name='Quantidade Máxima de Parcelas'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='quantidade_minima_parcelas',
            field=models.IntegerField(blank=True, null=True, verbose_name='Quantidade Mínima de Parcelas'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='taxa_maxima',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Taxa Maxima'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='taxa_minima',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Taxa Minima'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_de_seguranca_proposta',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor de Segurança da Proposta'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_maximo_emprestimo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Máximo do Emprestimo'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_maximo_parcela',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Máximo da Parcela'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_minimo_emprestimo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Mínimo do Emprestimo'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_minimo_parcela',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Mínimo da Parcela'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='valor_tac',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='TAC'),
        ),
    ]
