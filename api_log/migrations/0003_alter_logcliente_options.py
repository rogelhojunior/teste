# Generated by Django 4.1.3 on 2023-04-24 20:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api_log', '0002_remove_averbacao_cliente_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='logcliente',
            options={'verbose_name': 'Log - Cliente', 'verbose_name_plural': 'Log - Clientes'},
        ),
    ]
