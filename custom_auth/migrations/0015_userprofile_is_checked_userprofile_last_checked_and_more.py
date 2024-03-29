# Generated by Django 4.2.2 on 2023-08-07 17:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0014_alter_userprofile_is_staff'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_checked',
            field=models.BooleanField(default=False, verbose_name='Verificado?'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='last_checked',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Última verificação'),
        ),
        migrations.CreateModel(
            name='AnexoUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_anexo', models.SmallIntegerField(blank=True, choices=[(1, 'CCB'), (2, 'Documento do cliente frente'), (3, 'Documento do cliente verso'), (12, 'Documentos Adicionais'), (4, 'Selfie'), (5, 'Foto da Prova de Vida'), (6, 'Comprovante de endereço'), (7, 'Comprovante financeiro'), (11, 'Repasse'), (22, 'Arquivo retorno reserva'), (8, 'Documento - CNH'), (13, 'Documento Frente - CNH'), (14, 'Documento Verso - CNH'), (15, 'Termos e assinaturas')], null=True, verbose_name='Tipo do anexo')),
                ('nome_anexo', models.CharField(max_length=300, verbose_name='Nome do anexo')),
                ('anexo_extensao', models.CharField(max_length=10, verbose_name='Código extensão')),
                ('anexo_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL do documento')),
                ('arquivo', models.FileField(blank=True, null=True, upload_to='cliente', verbose_name='Documento')),
                ('anexado_em', models.DateTimeField(auto_now_add=True, verbose_name='Anexado em')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Usuário - Anexo',
                'verbose_name_plural': 'Usuário - Anexos',
            },
        ),
    ]
