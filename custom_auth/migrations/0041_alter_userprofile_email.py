# Generated by Django 4.2.3 on 2024-01-22 12:27

from django.db import migrations, models
from django.db.models import Count


def fix_duplicate_emails(apps, schema_editor):
    UserProfile = apps.get_model('custom_auth', 'UserProfile')

    duplicate_emails = (
        UserProfile.objects
        .values('email')
        .annotate(email_count=Count('id'))
        .filter(email_count__gt=1)
    )

    for entry in duplicate_emails:
        duplicate_users = UserProfile.objects.filter(email=entry['email'])
        for user in duplicate_users[1:]:
            user.email = None  # Definindo os e-mails duplicados como null
            user.save()


class Migration(migrations.Migration):
    dependencies = [
        ('custom_auth', '0040_alter_userprofile_numero_febraban'),
    ]
    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='email',
            field=models.EmailField(blank=True, null=True, max_length=255),
        ),
        migrations.RunPython(fix_duplicate_emails),
    ]
