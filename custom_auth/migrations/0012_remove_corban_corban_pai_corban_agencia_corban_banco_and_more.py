# Generated by Django 4.2.2 on 2023-07-20 20:44

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_comercial', '0007_remove_cadastrolojas_representante_comercial_and_more'),
        ('custom_auth', '0011_userprofile_media_segundos_digitacao'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='corban',
            name='corban_pai',
        ),
        migrations.AddField(
            model_name='corban',
            name='agencia',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Número da agência'),
        ),
        migrations.AddField(
            model_name='corban',
            name='banco',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Número do banco'),
        ),
        migrations.AddField(
            model_name='corban',
            name='conta',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Número da conta'),
        ),
        migrations.AddField(
            model_name='corban',
            name='loja_matriz',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Número da Loja Matriz'),
        ),
        migrations.AddField(
            model_name='corban',
            name='nome_representante',
            field=models.CharField(max_length=200, null=True, verbose_name='Nome Completo'),
        ),
        migrations.AddField(
            model_name='corban',
            name='nu_cpf_cnpj_representante',
            field=models.CharField(max_length=14, null=True, unique=True, verbose_name='Número de CPF/CNPJ'),
        ),
        migrations.AddField(
            model_name='corban',
            name='produtos',
            field=models.ManyToManyField(to='custom_auth.produtos', verbose_name='Produtos'),
        ),
        migrations.AddField(
            model_name='corban',
            name='representante_comercial',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gestao_comercial.representantecomercial', verbose_name='Representante Comercial'),
        ),
        migrations.AddField(
            model_name='corban',
            name='telefone',
            field=models.CharField(blank=True, max_length=11, null=True, validators=[django.core.validators.RegexValidator(message='Número de telefone inválido. O formato deve ser: 00123456789', regex='^\\d{11}$')], verbose_name='Telefone da Loja'),
        ),
        migrations.AddField(
            model_name='corban',
            name='telefone_representante',
            field=models.CharField(max_length=11, null=True, validators=[django.core.validators.RegexValidator(message='Número de telefone inválido. O formato deve ser: 00123456789', regex='^\\d{11}$')], verbose_name='Telefone de Contato'),
        ),
        migrations.AddField(
            model_name='corban',
            name='tipo_cadastro',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Matriz'), (2, 'Subsidiária'), (3, 'Subestabelecimento')], null=True, verbose_name='Tipo de Cadastro'),
        ),
        migrations.AddField(
            model_name='corban',
            name='tipo_estabelecimento',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Virtual'), (2, 'Físico')], null=True, verbose_name='Tipo de Estabelecimento'),
        ),
        migrations.AddField(
            model_name='corban',
            name='tipo_relacionamento',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Proprietário'), (2, 'Representante Legal'), (3, 'Representante Autorizado')], null=True, verbose_name='Tipo de Relacionamento'),
        ),
        migrations.AddField(
            model_name='corban',
            name='tipo_venda',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'B2C - Direto ao Cliente'), (2, 'B2B2C - Comercial')], null=True, verbose_name='Tipo de Venda'),
        ),
        migrations.AlterField(
            model_name='corban',
            name='corban_CNPJ',
            field=models.CharField(max_length=250, null=True, unique=True, verbose_name='Número de CPF/CNPJ'),
        ),
        migrations.AlterField(
            model_name='corban',
            name='corban_email',
            field=models.CharField(max_length=250, null=True, verbose_name='E-mail Coorporativo'),
        ),
        migrations.AlterField(
            model_name='corban',
            name='corban_endereco',
            field=models.CharField(max_length=250, null=True, verbose_name='Endereço Completo'),
        ),
    ]
