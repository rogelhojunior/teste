# Generated by Django 4.1.3 on 2023-04-21 20:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contract', '0001_initial'),
        ('core', '0001_initial'),
        ('consignado_inss', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='logwebhookqitech',
            name='contrato',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contract.contrato', verbose_name='Contrato'),
        ),
        migrations.AddField(
            model_name='dadosin100',
            name='cliente',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.cliente', verbose_name='Cliente'),
        ),
    ]
