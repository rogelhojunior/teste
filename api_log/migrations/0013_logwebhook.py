# Generated by Django 4.2.2 on 2023-06-30 14:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_log', '0012_banksoft_tipo_chamada'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogWebhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chamada_webhook', models.CharField(blank=True, max_length=300, null=True, verbose_name='Tipo da Chamada')),
                ('log_webhook', models.TextField(blank=True, null=True, verbose_name='Payload de resposta')),
                ('criado_em', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Criado em')),
            ],
            options={
                'verbose_name': 'Log - Webhook',
                'verbose_name_plural': 'Log - Webhook',
            },
        ),
    ]
