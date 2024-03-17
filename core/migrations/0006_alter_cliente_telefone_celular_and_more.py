# Generated by Django 4.1.3 on 2023-04-26 19:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_parametrosbackoffice_tipoproduto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='telefone_celular',
            field=models.CharField(blank=True, max_length=15, null=True, verbose_name='DDD + número com 9 dígitos'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='telefone_residencial',
            field=models.CharField(blank=True, max_length=15, null=True, verbose_name='DDD + número com 8 dígitos'),
        ),
    ]
