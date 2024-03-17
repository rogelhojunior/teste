# Generated by Django 4.2.2 on 2023-07-19 14:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_aceitein100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aceitein100',
            name='data_aceite',
            field=models.DateField(auto_now_add=True, null=True, verbose_name='Data aceite'),
        ),
        migrations.AlterField(
            model_name='aceitein100',
            name='data_criacao_token',
            field=models.DateField(null=True, verbose_name='Data de criação do Token'),
        ),
        migrations.AlterField(
            model_name='aceitein100',
            name='data_vencimento_aceite',
            field=models.DateField(null=True, verbose_name='Data de vencimento do aceite'),
        ),
        migrations.AlterField(
            model_name='aceitein100',
            name='data_vencimento_token',
            field=models.DateField(null=True, verbose_name='Data de vencimento do Token'),
        ),
        migrations.CreateModel(
            name='DocumentoAceiteIN100',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_anexo', models.CharField(max_length=300, verbose_name='Nome do anexo')),
                ('anexo_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL do documento')),
                ('criado_em', models.DateField(auto_now_add=True, verbose_name='Criado em')),
                ('aceite_in100', models.ForeignKey(max_length=100, on_delete=django.db.models.deletion.CASCADE, to='core.aceitein100', verbose_name='Aceite IN100')),
            ],
            options={
                'verbose_name': 'Aceite IN100',
                'verbose_name_plural': '6. Aceite IN100',
            },
        ),
    ]
