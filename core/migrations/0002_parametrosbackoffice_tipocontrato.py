# Generated by Django 4.1.3 on 2023-04-22 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosbackoffice',
            name='tipoContrato',
            field=models.SmallIntegerField(choices=[(1, 'Operação nova (margem livre)'), (2, 'Refinanciamento'), (3, 'Refin Portabilidade'), (4, 'Portabilidade'), (5, 'Novo Aumento Salarial')], default=4, verbose_name='Tipo de Contrato'),
        ),
    ]
