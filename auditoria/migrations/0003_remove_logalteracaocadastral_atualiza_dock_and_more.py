# Generated by Django 4.2.2 on 2023-07-18 20:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_parametrosproduto_dia_vencimento_padrao_simulacao_and_more'),
        ('auditoria', '0002_alter_logalteracaocadastral_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='atualiza_dock',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='canal',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='data_hora',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='novo_registro',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='registro_anterior',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='tipo_registro',
        ),
        migrations.RemoveField(
            model_name='logalteracaocadastral',
            name='usuario',
        ),
        migrations.AddField(
            model_name='logalteracaocadastral',
            name='cliente',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='core.cliente', verbose_name='Cliente'),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='LogAlteracaoCadastralDock',
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
                'verbose_name': 'Histórico de alteração',
                'verbose_name_plural': 'Histórico de alterações',
            },
        ),
    ]
