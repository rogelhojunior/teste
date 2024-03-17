# Generated by Django 4.2.3 on 2024-01-03 20:26

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0079_alter_parametrosproduto_prazo_maximo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosproduto',
            name='taxa_minima_recalculo',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                verbose_name='Taxa minima do recálculo',
            ),
        ),
    ]
