# Generated by Django 4.1.3 on 2023-04-27 15:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0021_alter_cartaobeneficio_contrato'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='enviado_comprovante_residencia',
        ),
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='enviado_documento_pessoal',
        ),
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='pendente_documento',
        ),
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='pendente_endereco',
        ),
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='selfie_enviada',
        ),
        migrations.RemoveField(
            model_name='cartaobeneficio',
            name='selfie_pendente',
        ),
        migrations.AddField(
            model_name='contrato',
            name='enviado_comprovante_residencia',
            field=models.BooleanField(default=False, verbose_name='Comprovante de residência enviado?'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='enviado_documento_pessoal',
            field=models.BooleanField(default=False, verbose_name='Documento pessoal enviado?'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='pendente_documento',
            field=models.BooleanField(default=False, verbose_name='Documento pessoal pendente?'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='pendente_endereco',
            field=models.BooleanField(default=False, verbose_name='Comprovante de residência pendente?'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='selfie_enviada',
            field=models.BooleanField(default=False, verbose_name='Selfie enviada?'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='selfie_pendente',
            field=models.BooleanField(default=False, verbose_name='Selfie pendente?'),
        ),
    ]
