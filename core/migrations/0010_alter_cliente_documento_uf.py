# Generated by Django 4.1.3 on 2023-04-28 13:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_merge_20230428_0948'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='documento_uf',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'AC'), (2, 'AL'), (3, 'AP'), (4, 'AM'), (5, 'BA'), (6, 'CE'), (7, 'DF'), (8, 'ES'), (9, 'GO'), (10, 'MA'), (11, 'MT'), (12, 'MS'), (13, 'MG'), (14, 'PA'), (15, 'PB'), (16, 'PR'), (17, 'PE'), (18, 'PI'), (19, 'RJ'), (20, 'RN'), (21, 'RS'), (22, 'RO'), (23, 'RR'), (24, 'SC'), (25, 'SP'), (26, 'SE'), (27, 'TO')], null=True, verbose_name='UF de emissão do documento'),
        ),
    ]
