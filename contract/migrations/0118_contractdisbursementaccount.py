# Generated by Django 4.2.3 on 2023-10-24 17:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('contract', '0117_alter_cartaobeneficio_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractDisbursementAccount',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('url', models.URLField(blank=True, max_length=500, null=True)),
                (
                    'amount',
                    models.DecimalField(
                        blank=True, decimal_places=5, max_digits=12, null=True
                    ),
                ),
                ('description', models.TextField(blank=True, null=True)),
                (
                    'transaction_key',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'origin_transaction_key',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_name',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_type',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_branch',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_purpose',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_document',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_bank_ispb',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_branch_digit',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_account_digit',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'destination_account_number',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ('payment_date', models.DateTimeField()),
                (
                    'free_margin',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='disbursement_account',
                        to='contract.margemlivre',
                    ),
                ),
            ],
        ),
    ]
