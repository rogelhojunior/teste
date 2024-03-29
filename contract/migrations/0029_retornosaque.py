# Generated by Django 4.1.3 on 2023-05-02 19:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0028_alter_validacaocontrato_retorno_hub'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetornoSaque',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('NumeroProposta', models.CharField(max_length=300, null=True, verbose_name='Número da proposta')),
                ('valorTED', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Valor TED')),
                ('Status', models.CharField(max_length=300, null=True, verbose_name='Status')),
                ('Banco', models.CharField(max_length=300, null=True, verbose_name='Banco')),
                ('Agencia', models.CharField(max_length=300, null=True, verbose_name='Agência')),
                ('Conta', models.CharField(max_length=300, null=True, verbose_name='Conta')),
                ('DVConta', models.CharField(max_length=300, null=True, verbose_name='Dígito Verificador')),
                ('CPFCNPJ', models.CharField(max_length=300, null=True, verbose_name='CPF / CNPJ')),
                ('DtCriacao', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('contrato', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contract.contrato')),
            ],
            options={
                'verbose_name': '6. Retorno Saque',
                'verbose_name_plural': '6. Retorno Saque',
            },
        ),
    ]
