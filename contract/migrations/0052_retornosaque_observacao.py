# Generated by Django 4.1.3 on 2023-05-17 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0051_cartaobeneficio_numero_proposta_banksoft'),
    ]

    operations = [
        migrations.AddField(
            model_name='retornosaque',
            name='Observacao',
            field=models.TextField(blank=True, null=True, verbose_name='Observacao'),
        ),
    ]
