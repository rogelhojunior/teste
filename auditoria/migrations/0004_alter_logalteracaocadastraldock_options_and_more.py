# Generated by Django 4.2.2 on 2023-07-28 17:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0003_remove_logalteracaocadastral_atualiza_dock_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='logalteracaocadastraldock',
            options={'verbose_name': 'Histórico de alteração - DOCK', 'verbose_name_plural': 'Histórico de alterações - DOCK'},
        ),
        migrations.CreateModel(
            name='LogAlteracaoCadastralDadosCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_registro', models.CharField(max_length=20, verbose_name='Tipo de Registro')),
                ('registro_anterior', models.CharField(max_length=300, verbose_name='Registro Anterior')),
                ('novo_registro', models.CharField(max_length=300, verbose_name='Novo Registro')),
                ('usuario', models.CharField(max_length=300, verbose_name='Usuário')),
                ('canal', models.CharField(max_length=300, verbose_name='Canal')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('log_cadastral', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auditoria.logalteracaocadastral', verbose_name='Alteração Cadastral')),
            ],
            options={
                'verbose_name': 'Histórico de alteração - Dados Bancários',
                'verbose_name_plural': 'Histórico de alterações - Dados Bancários',
            },
        ),
    ]
