# Generated by Django 4.2.2 on 2023-08-15 17:35


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0097_merge_20230810_1013'),
    ]

    operations = [
        migrations.AddField(
            model_name='portabilidade',
            name='codigo_dataprev',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Código Dataprev'),
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='descricao_dataprev',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Descrição Dataprev'),
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='dt_retorno_dataprev',
            field=models.DateField(blank=True, null=True, verbose_name='Data de retorno do Dataprev'),
        ),
    ]
