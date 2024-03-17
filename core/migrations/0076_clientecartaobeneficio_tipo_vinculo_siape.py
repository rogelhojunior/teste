# Generated by Django 4.2.3 on 2023-12-04 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_clientecartaobeneficio_classificacao_siape_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='tipo_vinculo_siape',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Servidor'), (2, 'Pencionista')], null=True, verbose_name='Tipo de Vinculo - SIAPE'),
        ),
    ]
