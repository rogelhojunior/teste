# Generated by Django 4.1.3 on 2023-06-12 13:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0069_alter_contrato_cd_contrato_tipo_saquecomplementar'),
    ]

    operations = [
        migrations.AddField(
            model_name='saquecomplementar',
            name='apto_saque',
            field=models.BooleanField(default=True, verbose_name='Apto saque?'),
        ),
    ]
