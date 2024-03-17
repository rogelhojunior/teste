# Generated by Django 4.2.2 on 2023-06-19 12:59

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0036_remove_anexocliente_arquivo'),
    ]

    operations = [
        migrations.AddField(
            model_name="Cliente",
            name="id_unico",
            field=models.UUIDField(default=uuid.uuid4, null=True),
        ),
    ]
