# Generated by Django 4.1.3 on 2023-05-10 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0048_alter_portabilidade_status_ccb'),
    ]

    operations = [
        migrations.AddField(
            model_name='portabilidade',
            name='related_party_key',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Related_Party_Key'),
        ),
    ]
