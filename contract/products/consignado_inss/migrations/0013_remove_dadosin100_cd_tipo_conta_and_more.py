# Generated by Django 4.2.2 on 2023-06-19 13:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('consignado_inss', '0012_remove_dadosin100_contrato'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dadosin100',
            name='cd_tipo_conta',
        ),
        migrations.RemoveField(
            model_name='dadosin100',
            name='codigo_banco',
        ),
        migrations.RemoveField(
            model_name='dadosin100',
            name='numero_agencia',
        ),
        migrations.RemoveField(
            model_name='dadosin100',
            name='numero_conta',
        ),
        migrations.RemoveField(
            model_name='dadosin100',
            name='numero_digito',
        ),
    ]
