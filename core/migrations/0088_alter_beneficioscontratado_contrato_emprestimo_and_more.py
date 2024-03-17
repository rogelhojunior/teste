# Generated by Django 4.2.3 on 2024-01-19 03:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('contract', '0153_alter_cartaobeneficio_convenio_and_more'),
        ('cartao_beneficio', '0058_alter_planos_seguradora'),
        ('core', '0087_parametrosproduto_teto_inss'),
    ]

    operations = [
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='contrato_emprestimo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='contract.contrato',
                verbose_name='contrato vinculado',
            ),
        ),
        migrations.AlterField(
            model_name='beneficioscontratado',
            name='plano',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='beneficio_planos_contratados',
                to='cartao_beneficio.planos',
                verbose_name='Planos',
            ),
        ),
        migrations.AlterField(
            model_name='clientecartaobeneficio',
            name='contrato',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cliente_cartao_contrato',
                to='contract.contrato',
                verbose_name='Contrato',
            ),
        ),
        migrations.AlterField(
            model_name='clientecartaobeneficio',
            name='convenio',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cliente_convenio',
                to='cartao_beneficio.convenios',
                verbose_name='Convenio',
            ),
        ),
        migrations.AlterField(
            model_name='representantelegal',
            name='representanteLegal',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='representante',
                to='core.cliente',
                verbose_name='Cliente',
            ),
        ),
    ]
