# Generated by Django 4.2.2 on 2023-06-23 16:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_log', '0011_retornosdock_payload_envio'),
    ]

    operations = [
        migrations.AddField(
            model_name='banksoft',
            name='tipo_chamada',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tipo chamada'),
        ),
    ]
