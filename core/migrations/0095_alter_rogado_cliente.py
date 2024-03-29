# Generated by Django 4.2.3 on 2024-03-05 20:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0094_cliente_escolaridade_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rogado",
            name="cliente",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rogados",
                to="core.cliente",
                verbose_name="Cliente",
            ),
        ),
    ]
