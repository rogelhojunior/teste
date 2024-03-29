# Generated by Django 4.2.2 on 2023-06-15 17:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_remove_parametrosproduto_comprovante_residencia_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnexoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_anexo', models.CharField(max_length=300, verbose_name='Nome do anexo')),
                ('anexo_extensao', models.CharField(max_length=10, verbose_name='Código extensão')),
                ('anexo_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL do documento')),
                ('arquivo', models.FileField(blank=True, null=True, upload_to='cliente', verbose_name='Documento')),
                ('anexado_em', models.DateTimeField(auto_now_add=True, verbose_name='Anexado em')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.cliente', verbose_name='Cliente')),
            ],
            options={
                'verbose_name': 'Cliente - Anexo',
                'verbose_name_plural': 'Cliente - Anexos',
            },
        ),
    ]
