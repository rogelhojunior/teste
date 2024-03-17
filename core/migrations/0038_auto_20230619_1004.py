from django.db import migrations
import uuid


def gen_uuid(apps, schema_editor):
    Cliente = apps.get_model("core", "Cliente")
    for row in Cliente.objects.all():
        row.id_unico = uuid.uuid4()
        row.save(update_fields=["id_unico"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0037_cliente_id_unico"),
    ]

    operations = [
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
    ]
