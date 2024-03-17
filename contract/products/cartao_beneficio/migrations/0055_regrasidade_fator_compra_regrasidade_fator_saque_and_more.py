# Generated by Django 4.2.3 on 2024-01-04 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0054_convenios_derivacao_mesa_averbacao_regrasidade_fator_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrasidade',
            name='fator_compra',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Fator de multiplicação de compra'),
        ),
        migrations.AddField(
            model_name='regrasidade',
            name='fator_saque',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Fator de multiplicação de saque'),
        ),
    ]
