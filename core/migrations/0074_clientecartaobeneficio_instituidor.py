# Generated by Django 4.2.3 on 2023-11-30 14:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_clientecartaobeneficio_folha_compra_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientecartaobeneficio',
            name='instituidor',
            field=models.CharField(blank=True, max_length=12, null=True, verbose_name='Instituidor'),
        ),
    ]
