# Generated by Django 4.2.2 on 2023-07-05 19:38

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_comercial', '0003_alter_cadastrolojas_options_cadastrolojas_agencia_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='representantecomercial',
            options={'verbose_name': 'Representante Comercial', 'verbose_name_plural': '1. Representantes Comerciais'},
        ),
        migrations.AddField(
            model_name='cadastrolojas',
            name='nome_representante',
            field=models.CharField(max_length=200, null=True, verbose_name='Nome Completo'),
        ),
        migrations.AddField(
            model_name='cadastrolojas',
            name='nu_cpf_cnpj_representante',
            field=models.CharField(max_length=14, null=True, unique=True, verbose_name='Número de CPF/CNPJ'),
        ),
        migrations.AddField(
            model_name='cadastrolojas',
            name='telefone_representante',
            field=models.CharField(max_length=11, null=True, validators=[django.core.validators.RegexValidator(message='Número de telefone inválido. O formato deve ser: 00123456789', regex='^\\d{11}$')], verbose_name='Telefone de Contato'),
        ),
        migrations.AlterField(
            model_name='agente',
            name='representante_comercial',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gestao_comercial.representantecomercial', verbose_name='Representante Comercial'),
        ),
        migrations.AlterField(
            model_name='cadastrolojas',
            name='email',
            field=models.CharField(max_length=250, null=True, verbose_name='E-mail Coorporativo'),
        ),
        migrations.AlterField(
            model_name='cadastrolojas',
            name='nome',
            field=models.CharField(max_length=200, null=True, verbose_name='Nome Completo'),
        ),
        migrations.AlterField(
            model_name='cadastrolojas',
            name='nu_cpf_cnpj',
            field=models.CharField(max_length=14, null=True, unique=True, verbose_name='Número de CPF/CNPJ'),
        ),
        migrations.AlterField(
            model_name='cadastrolojas',
            name='telefone',
            field=models.CharField(blank=True, max_length=11, null=True, validators=[django.core.validators.RegexValidator(message='Número de telefone inválido. O formato deve ser: 00123456789', regex='^\\d{11}$')], verbose_name='Telefone da Loja'),
        ),
        migrations.AlterField(
            model_name='gerente',
            name='representante_comercial',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gestao_comercial.representantecomercial', verbose_name='Representante Comercial'),
        ),
        migrations.AlterField(
            model_name='localatuacao',
            name='estado',
            field=models.SmallIntegerField(choices=[(1, 'AC'), (2, 'AL'), (3, 'AP'), (4, 'AM'), (5, 'BA'), (6, 'CE'), (7, 'DF'), (8, 'ES'), (9, 'GO'), (10, 'MA'), (11, 'MT'), (12, 'MS'), (13, 'MG'), (14, 'PA'), (15, 'PB'), (16, 'PR'), (17, 'PE'), (18, 'PI'), (19, 'RJ'), (20, 'RN'), (21, 'RS'), (22, 'RO'), (23, 'RR'), (24, 'SC'), (25, 'SP'), (26, 'SE'), (27, 'TO')], null=True, verbose_name='Estado'),
        ),
        migrations.AlterField(
            model_name='localatuacao',
            name='municipio',
            field=models.CharField(max_length=200, null=True, verbose_name='Município'),
        ),
        migrations.AlterField(
            model_name='localatuacao',
            name='regiao',
            field=models.SmallIntegerField(choices=[(1, 'Norte'), (2, 'Nordeste'), (3, 'Centro-Oeste'), (4, 'Sul'), (5, 'Sudeste')], null=True, verbose_name='Região'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='cargo',
            field=models.SmallIntegerField(choices=[(1, 'Agente'), (2, 'Gerente'), (3, 'Superintendente')], null=True, verbose_name='Cargo'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='email',
            field=models.CharField(max_length=200, null=True, verbose_name='E-mail Corporativo'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='nome',
            field=models.CharField(max_length=200, null=True, verbose_name='Nome Completo'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='nu_cpf_cnpj',
            field=models.CharField(max_length=14, null=True, unique=True, verbose_name='Número de CPF/CNPJ'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='telefone',
            field=models.CharField(max_length=11, null=True, validators=[django.core.validators.RegexValidator(message='Número de telefone inválido. O formato deve ser: 00123456789', regex='^\\d{11}$')], verbose_name='DDD + número com 9 dígitos'),
        ),
        migrations.AlterField(
            model_name='representantecomercial',
            name='tipo_atuacao',
            field=models.SmallIntegerField(choices=[(1, 'Regional'), (2, 'Distrital')], null=True, verbose_name='Tipo de Atuação'),
        ),
        migrations.AlterField(
            model_name='superintendente',
            name='representante_comercial',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gestao_comercial.representantecomercial', verbose_name='Representante Comercial'),
        ),
        migrations.AlterField(
            model_name='superintendente',
            name='supervisor_direto',
            field=models.CharField(max_length=200, verbose_name='Supervisor Direto'),
        ),
    ]
