# Generated by Django 4.2.2 on 2023-08-14 02:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_beneficioscontratado_arquivogenerali'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosproduto',
            name='idade_especie_87',
            field=models.IntegerField(blank=True, help_text='Valor em anos', null=True, verbose_name='Idade maxima da Especie 87'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='prazo_maximo',
            field=models.IntegerField(blank=True, help_text='Valor em meses', null=True, verbose_name='Pazo maximo da proposta'),
        ),
        migrations.AddField(
            model_name='parametrosproduto',
            name='prazo_minimo',
            field=models.IntegerField(blank=True, help_text='Valor em meses', null=True, verbose_name='Pazo minimo da proposta'),
        ),
    ]
