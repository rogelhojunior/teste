# Generated by Django 4.1.3 on 2023-05-03 15:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0030_merge_20230503_1142'),
    ]

    operations = [
        migrations.AlterField(
            model_name='retornosaque',
            name='Agencia',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Agência'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='Banco',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Banco'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='CPFCNPJ',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='CPF / CNPJ'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='Conta',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Conta'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='DVConta',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Dígito Verificador'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='NumeroProposta',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Número da proposta'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='Status',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='retornosaque',
            name='valorTED',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=12, null=True, verbose_name='Valor TED'),
        ),
    ]
