# Generated by Django 4.1.3 on 2023-05-07 20:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [

        ('contract', '0038_merge_20230507_1635'),

    ]

    operations = [
        migrations.AlterField(
            model_name='portabilidade',
            name='chave_proposta',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Chave proposta'),
        ),
    ]
