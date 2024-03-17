from django.db import migrations

from core.choices import UFS

def populate_ufs(apps, schema_editor):
    UF = apps.get_model('documentscopy', 'UF')

    for uf, _ in UFS:
        UF.objects.create(uf=uf)

class Migration(migrations.Migration):

    dependencies = [
        ('documentscopy', '0014_uf_bpoconfig_age_from_bpoconfig_age_to_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_ufs),
    ]
