# Generated by Django 4.1.3 on 2023-05-10 14:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0043_alter_portabilidade_status_ccb'),
    ]

    operations = [
        migrations.AddField(
            model_name='portabilidade',
            name='document_key_QiTech',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Chave do Documento'),
        ),
    ]
