# Generated by Django 4.2.3 on 2023-09-19 20:33

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            'contract',
            '0109_margemlivre_alter_contrato_tipo_produto_delete_inss_and_more',
        ),
    ]

    operations = [
        migrations.AddField(
            model_name='portabilidade',
            name='dt_recusa_retido',
            field=models.DateField(
                blank=True,
                help_text='Data de recusa/retido (CIP)',
                null=True,
                verbose_name='Data de RECUSA/RETIDO',
            ),
        ),
    ]
