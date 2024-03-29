# Generated by Django 4.2.3 on 2023-12-22 19:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('contract', '0146_portabilidade_dt_primeiro_pagamento_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='refinanciamento',
            name='dt_primeiro_pagamento',
            field=models.DateField(
                blank=True,
                help_text='Data do primeiro pagamento',
                null=True,
                verbose_name='Data do primeiro pagamento',
            ),
        ),
        migrations.AddField(
            model_name='refinanciamento',
            name='dt_ultimo_pagamento',
            field=models.DateField(
                blank=True,
                help_text='Data do último pagamento',
                null=True,
                verbose_name='Data do último pagamento',
            ),
        ),
    ]
