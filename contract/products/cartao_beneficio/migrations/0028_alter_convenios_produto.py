# Generated by Django 4.2.2 on 2023-08-31 21:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0027_alter_convenios_averbadora'),
    ]

    operations = [
        migrations.AlterField(
            model_name='convenios',
            name='produto',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Saque Complementar'), (15, 'Cartão Consignado')], null=True, verbose_name='Produtos para a oferta'),
        ),
    ]
