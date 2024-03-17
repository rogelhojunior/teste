# Generated by Django 4.1.3 on 2023-05-10 14:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0044_portabilidade_document_key_qitech'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='portabilidade',
            name='document_key_QiTech',
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='document_key_QiTech_CCB',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Chave do Documento CCB'),
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='document_key_QiTech_Frente_ou_CNH',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Chave do Documento Pessoal Frente/CNH'),
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='document_key_QiTech_Verso',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Chave do Documento Pessoal Verso'),
        ),
    ]
