# Generated by Django 4.2.3 on 2024-02-21 19:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0161_alter_cartaobeneficio_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrato',
            name='contrato_cross_sell',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Contrato cross sell?'),
        ),
    ]
