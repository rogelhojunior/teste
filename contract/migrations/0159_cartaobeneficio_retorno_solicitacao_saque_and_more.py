# Generated by Django 4.2.3 on 2024-02-06 19:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0158_margemlivre_motivo_reapresentacao_pagamento_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartaobeneficio',
            name='retorno_solicitacao_saque',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Retorno solicitação saque'),
        ),
        migrations.AddField(
            model_name='saquecomplementar',
            name='retorno_solicitacao_saque',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Retorno solicitação saque'),
        ),
    ]
