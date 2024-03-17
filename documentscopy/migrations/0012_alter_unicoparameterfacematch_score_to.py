# Generated by Django 4.2.3 on 2024-01-24 19:28

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documentscopy", "0011_alter_unicoparameterfacematch_score_from"),
    ]

    operations = [
        migrations.AlterField(
            model_name="unicoparameterfacematch",
            name="score_to",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(-99.9),
                    django.core.validators.MaxValueValidator(1000),
                ],
                verbose_name="Até",
            ),
        ),
    ]
