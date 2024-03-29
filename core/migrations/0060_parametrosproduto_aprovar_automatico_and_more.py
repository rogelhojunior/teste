# Generated by Django 4.2.3 on 2023-09-08 17:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_alter_aceitein100_produto_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosproduto',
            name='aprovar_automatico',
            field=models.BooleanField(default=False, verbose_name='Aprovação Automática de Contratos?'),
        ),
        migrations.AlterField(
            model_name='arquivogenerali',
            name='sequencial',
            field=models.IntegerField(blank=True, null=True, verbose_name='Nº Seqüencial'),
        ),
    ]
