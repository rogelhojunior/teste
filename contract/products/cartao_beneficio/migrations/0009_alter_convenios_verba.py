# Generated by Django 4.1.3 on 2023-05-04 12:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0008_convenios_verba'),
    ]

    operations = [
        migrations.AlterField(
            model_name='convenios',
            name='verba',
            field=models.CharField(default=123, max_length=30, verbose_name='Número da Verba'),
            preserve_default=False,
        ),
    ]
