# Generated by Django 4.2.2 on 2023-08-03 17:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_log', '0017_alter_realizareserva_cliente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realizasimulacao',
            name='limite_pre_aprovado',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name='Valor do limite pré-aprovado'),
        ),
        migrations.AlterField(
            model_name='realizasimulacao',
            name='valor_financiado',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Financiado'),
        ),
        migrations.AlterField(
            model_name='realizasimulacao',
            name='valor_parcela',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor da parcela'),
        ),
        migrations.AlterField(
            model_name='realizasimulacao',
            name='valor_saque',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name='Valor do saque'),
        ),
    ]
