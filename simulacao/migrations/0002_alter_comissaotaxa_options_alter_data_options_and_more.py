from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulacao', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='comissaotaxa',
            options={'verbose_name': 'Taxa de Comissão', 'verbose_name_plural': '3. Taxas de Comissão'},
        ),
        migrations.AlterModelOptions(
            name='data',
            options={'verbose_name': 'Datas e Feriados', 'verbose_name_plural': '2. Datas e Feriados'},
        ),
        migrations.AlterModelOptions(
            name='faixaidade',
            options={'verbose_name': 'Faixa de Idade', 'verbose_name_plural': '1. Faixas de Idade'},
        ),
        migrations.AlterField(
            model_name='data',
            name='base',
            field=models.IntegerField(verbose_name=''),
        ),
        migrations.AlterField(
            model_name='data',
            name='ds_dia_da_semana',
            field=models.CharField(max_length=50, null=True, verbose_name='Dia da Semana'),
        ),
        migrations.AlterField(
            model_name='data',
            name='ds_feriado',
            field=models.CharField(max_length=50, null=True, verbose_name='Descrição do Feriado'),
        ),
        migrations.AlterField(
            model_name='data',
            name='ds_mes',
            field=models.CharField(max_length=50, null=True, verbose_name='Mês'),
        ),
        migrations.AlterField(
            model_name='data',
            name='dt_data',
            field=models.DateField(verbose_name='Data'),
        ),
        migrations.AlterField(
            model_name='data',
            name='dt_data_util',
            field=models.DateField(verbose_name='Data Útil'),
        ),
        migrations.AlterField(
            model_name='data',
            name='fl_dia_util',
            field=models.BooleanField(verbose_name='Dia Útil'),
        ),
        migrations.AlterField(
            model_name='data',
            name='fl_feriado',
            field=models.BooleanField(verbose_name='Feriado'),
        ),
        migrations.AlterField(
            model_name='data',
            name='fl_final_de_semana',
            field=models.BooleanField(verbose_name='Final de Semana'),
        ),
        migrations.AlterField(
            model_name='data',
            name='fl_ponto_facultativo',
            field=models.BooleanField(verbose_name='Ponto Facultativo'),
        ),
    ]
