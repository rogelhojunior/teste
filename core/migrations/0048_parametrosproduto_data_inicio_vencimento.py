# Generated by Django 4.2.2 on 2023-07-20 17:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_alter_documentoaceitein100_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosproduto',
            name='data_inicio_vencimento',
            field=models.IntegerField(blank=True, help_text='Dia do primeiro vencimento QITECH', null=True, verbose_name='Data Vencimento QITECH'),
        ),
    ]
