# Generated by Django 4.2.3 on 2023-11-20 20:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0127_refinanciamento_margem_liberada_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrato',
            name='is_ccb_generated',
            field=models.BooleanField(default=False, verbose_name='A CCB foi gerada?'),
        ),
    ]
