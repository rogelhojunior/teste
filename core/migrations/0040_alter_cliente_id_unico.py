# Generated by Django 4.2.2 on 2023-06-19 23:21

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_auto_20230619_1004'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='id_unico',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='ID Único'),
        ),
    ]
