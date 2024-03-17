from django.db import migrations

from contract.choices import TIPOS_PRODUTO

def populate_products(apps, schema_editor):
    Product = apps.get_model('documentscopy', 'Product')

    for tipo_produto, _ in TIPOS_PRODUTO:
        Product.objects.create(product=tipo_produto)

class Migration(migrations.Migration):

    dependencies = [
        ('documentscopy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_products),
    ]
