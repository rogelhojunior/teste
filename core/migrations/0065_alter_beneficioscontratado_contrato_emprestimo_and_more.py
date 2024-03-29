# Generated by Django 4.2.3 on 2023-10-10 18:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0114_margemlivre_cpf_dados_divergentes'),
        ('core', '0064_remove_beneficioscontratado_plano_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='contrato_emprestimo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contract.contrato', verbose_name='contrato vinculado'),
        ),
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='identificacao_segurado',
            field=models.CharField(blank=True, max_length=50, verbose_name='identificação do segurado'),
        ),
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='nome_plano',
            field=models.CharField(blank=True, max_length=150, verbose_name='Nome do Plano'),
        ),
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='premio',
            field=models.CharField(blank=True, max_length=50, verbose_name='premio'),
        ),
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='validade',
            field=models.CharField(blank=True, max_length=50, verbose_name='validade'),
        ),
    ]
