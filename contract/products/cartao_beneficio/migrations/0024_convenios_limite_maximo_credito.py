# Generated by Django 4.2.2 on 2023-08-02 14:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0023_alter_suborgao_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='convenios',
            name='limite_maximo_credito',
            field=models.DecimalField(decimal_places=10, default=0, max_digits=20, verbose_name='Limite máximo de crédito'),
        ),
    ]
