# Generated by Django 4.1.3 on 2023-04-22 17:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_parametrosbackoffice_tipocontrato'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='dt_nascimento',
            field=models.DateField(blank=True, null=True, verbose_name='Data de nascimento'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='estado_civil',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Estado civil'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='form_ed_financeira',
            field=models.BooleanField(blank=True, default=False, help_text='Utilizado no PAB', null=True, verbose_name='Questionário de Educação Financeira preenchido'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='naturalidade',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Cidade de Naturalidade do cliente'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='nome_mae',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Nome da mãe do cliente'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='nu_cpf',
            field=models.CharField(blank=True, max_length=14, null=True, verbose_name='Número CPF do cliente'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='possui_procurador',
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='ppe',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Pessoa Politicamente Exposta'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='sexo',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Sexo do cliente'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='telefone_celular',
            field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name='DDD + número com 9 dígitos'),
        ),
        migrations.AlterField(
            model_name='parametrosbackoffice',
            name='tipoProduto',
            field=models.SmallIntegerField(choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Consignado')], default=1, verbose_name='Tipo de Produto'),
        ),
    ]
