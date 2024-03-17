# Generated by Django 4.1.3 on 2023-04-25 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0013_remove_contrato_criando_por_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contrato',
            name='tipo_produto',
            field=models.SmallIntegerField(choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Consignado'), (9, 'Portabilidade')], default=1, verbose_name='Tipo de Produto'),
        ),
    ]
