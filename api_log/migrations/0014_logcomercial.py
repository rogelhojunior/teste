# Generated by Django 4.2.2 on 2023-07-03 16:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api_log', '0013_logwebhook'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogComercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('representante_comercial', models.CharField(max_length=200, verbose_name='Nome do Representante Comercial')),
                ('cpf_cnpj', models.CharField(max_length=200, verbose_name='CPF/CNPJ do Representante Comercial')),
                ('cargo', models.SmallIntegerField(blank=True, choices=[(1, 'Agente'), (2, 'Gerente'), (3, 'Superintendente')], null=True, verbose_name='Cargo')),
                ('operacao', models.CharField(max_length=20, verbose_name='Operação')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Log - Representante Comercial',
                'verbose_name_plural': 'Logs - Representantes Comerciais',
            },
        ),
    ]
