# Generated by Django 4.1.3 on 2023-05-22 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0053_portabilidade_parcela_digitada'),
    ]

    operations = [
        migrations.AlterField(
            model_name='portabilidade',
            name='numero_contrato',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Número Contrato'),
        ),
    ]
