# Generated by Django 4.1.3 on 2023-05-07 14:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0034_alter_contrato_tipo_produto'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='inss',
            name='vr_liberado_cliente',
        ),
    ]
