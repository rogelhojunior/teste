# Generated by Django 4.1.3 on 2023-05-31 17:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_bancosbrasileiros_produto_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrosproduto',
            name='geolocalizacao_exigida',
            field=models.BooleanField(default=True, verbose_name='Geolocalização Exigida'),
        ),
    ]
