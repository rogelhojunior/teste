# Generated by Django 4.1.3 on 2023-06-07 15:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0007_produtos_tipo_produto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produtos',
            name='tipo_produto',
            field=models.SmallIntegerField(choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Cartão Benefício - Saque Complementar')], default=1, verbose_name='Tipo de Produto'),
        ),
    ]
