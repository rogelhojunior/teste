# Generated by Django 4.2.2 on 2023-06-15 21:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_anexocliente'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='anexocliente',
            name='arquivo',
        ),
    ]
