# Generated by Django 4.2.2 on 2023-07-11 14:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0082_cartaobeneficio_valor_parcela_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cartaobeneficio',
            name='possui_saque',
            field=models.BooleanField(default=True, verbose_name='Possui Saque Rotativo?'),
        ),
        migrations.AlterField(
            model_name='cartaobeneficio',
            name='saque_parcelado',
            field=models.BooleanField(default=False, verbose_name='Possui Saque Parcelado?'),
        ),
    ]
