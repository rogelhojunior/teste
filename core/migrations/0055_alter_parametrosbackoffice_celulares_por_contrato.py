# Generated by Django 4.2.2 on 2023-08-22 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_alter_aceitein100_produto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='parametrosbackoffice',
            name='celulares_por_contrato',
            field=models.IntegerField(default=2, null=True, verbose_name='Número de telefones iguais permitidos por CPF'),
        ),
    ]
