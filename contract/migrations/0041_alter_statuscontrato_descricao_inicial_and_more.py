# Generated by Django 4.1.3 on 2023-05-08 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0040_merge_20230508_1014'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statuscontrato',
            name='descricao_inicial',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Descrição Inicial'),
        ),
        migrations.AlterField(
            model_name='statuscontrato',
            name='descricao_mesa',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Descrição da Mesa'),
        ),
        migrations.AlterField(
            model_name='statuscontrato',
            name='descricao_originacao',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Descrição Originação'),
        ),
    ]
