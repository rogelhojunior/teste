# Generated by Django 4.2.3 on 2024-01-06 13:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0055_regrasidade_fator_compra_regrasidade_fator_saque_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='seguradoras',
            name='nome',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Tem Saúde'), (2, 'Generali'), (3, 'Sabemi')], null=True, verbose_name='Nome'),
        ),
    ]
