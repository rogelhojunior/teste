# Generated by Django 4.1.3 on 2023-05-08 19:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_log", "0009_qitechretornos_criado_em"),
    ]

    operations = [
        migrations.AddField(
            model_name="qitechretornos",
            name="tipo",
            field=models.CharField(
                blank=True, max_length=50, null=True, verbose_name="Tipo de chamada"
            ),
        ),
    ]
