# Generated by Django 4.2.3 on 2023-10-20 20:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0023_remove_userprofile_confia_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='possui_chat_suporte',
            field=models.BooleanField(default=False, verbose_name='Possui suporte por chat ?'),
        ),
    ]
