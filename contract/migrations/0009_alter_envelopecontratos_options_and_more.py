# Generated by Django 4.1.3 on 2023-04-24 20:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0008_delete_taxa'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='envelopecontratos',
            options={'verbose_name': 'Envelope', 'verbose_name_plural': '2. Envelopes'},
        ),
        migrations.RemoveField(
            model_name='portabilidade',
            name='antiga_parcela',
        ),
    ]
