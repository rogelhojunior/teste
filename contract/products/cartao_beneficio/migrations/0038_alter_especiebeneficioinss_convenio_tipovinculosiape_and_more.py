# Generated by Django 4.2.3 on 2023-10-20 15:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0037_convenios_aviso_reducao_margem_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='especiebeneficioinss',
            name='convenio',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='convenio_especie', to='cartao_beneficio.convenios', verbose_name='Convênio'),
        ),
        migrations.CreateModel(
            name='TipoVinculoSiape',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=255, verbose_name='Código')),
                ('descricao', models.CharField(max_length=255, verbose_name='Descrição')),
                ('permite_contratacao', models.BooleanField(default=False, verbose_name='Permite contratação?')),
                ('convenio', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='cartao_beneficio.convenios', verbose_name='Convênio')),
            ],
            options={
                'verbose_name': 'Tipo de Vínculo – SIAPE',
                'verbose_name_plural': 'Tipo de Vínculo – SIAPE',
            },
        ),
        migrations.CreateModel(
            name='ConvenioSiape',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.IntegerField(default=0, verbose_name='Código')),
                ('descricao', models.CharField(max_length=255, verbose_name='Descrição')),
                ('permite_contratacao', models.BooleanField(default=False, verbose_name='Permite contratação?')),
                ('convenio', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='cartao_beneficio.convenios', verbose_name='Convênio')),
            ],
            options={
                'verbose_name': 'Convênio – SIAPE',
                'verbose_name_plural': 'Convênio – SIAPE',
            },
        ),
        migrations.CreateModel(
            name='ClassificacaoSiape',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.IntegerField(default=0, verbose_name='Código')),
                ('descricao', models.CharField(max_length=255, verbose_name='Descrição')),
                ('permite_contratacao', models.BooleanField(default=False, verbose_name='Permite contratação?')),
                ('convenio', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='cartao_beneficio.convenios', verbose_name='Convênio')),
            ],
            options={
                'verbose_name': 'Classificação – SIAPE',
                'verbose_name_plural': 'Classificação – SIAPE',
            },
        ),
    ]
