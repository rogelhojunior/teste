# Generated by Django 4.2.2 on 2023-08-28 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_aceitein100_nome_cliente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aceitein100',
            name='nome_cliente',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Nome do Cliente'),
        ),
    ]
