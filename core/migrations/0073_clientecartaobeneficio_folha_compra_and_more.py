# Generated by Django 4.2.3 on 2023-11-30 12:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_alter_clientecartaobeneficio_tipo_margem'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='folha_compra',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Folha Compra'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='folha_saque',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Folha Saque'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='limite_pre_aprovado',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name='Valor do limite pré-aprovado'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='limite_pre_aprovado_compra',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name='Valor do limite pré-aprovado (Margem Compra)'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='limite_pre_aprovado_saque',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name='Valor do limite pré-aprovado (Margem Saque)'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='margem_compra',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Margem compra'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='margem_saque',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Margem saque'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='reserva_compra',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Número da Reserva (Margem Compra)'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='reserva_saque',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Número da Reserva (Margem Saque)'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='verba_compra',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Verba Compra'),
        ),
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='verba_saque',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Verba Saque'),
        ),
        migrations.AlterField(
            model_name='clientecartaobeneficio',
            name='tipo_margem',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Margem Compra'), (2, 'Margem Saque'), (3, 'Margem Unica'), (4, 'Margem Unificada')], null=True, verbose_name='Tipo Margem'),
        ),
    ]
