# Generated by Django 4.2.2 on 2023-07-25 19:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consignado_inss', '0016_dadosin100_tipo_retorno'),
    ]

    operations = [
        migrations.CreateModel(
            name='EspecieIN100',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_especie', models.IntegerField(blank=True, null=True, verbose_name='Número Espécie')),
                ('nome_especie', models.CharField(max_length=255, verbose_name='Nome Especie')),
                ('tipo_produto', models.SmallIntegerField(blank=True, choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Saque Complementar')], null=True, verbose_name='Tipo Produto')),
            ],
            options={
                'verbose_name': 'Espécie IN100',
                'verbose_name_plural': '1. Espécies IN100',
            },
        ),
        migrations.RemoveField(
            model_name='dadosin100',
            name='utlimo_exame_medico',
        ),
        migrations.AddField(
            model_name='dadosin100',
            name='ultimo_exame_medico',
            field=models.DateField(blank=True, null=True, verbose_name='Data da última Auditoria realizada pelo INSS'),
        ),
    ]
