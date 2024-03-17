# Generated by Django 4.2.3 on 2023-09-20 23:19

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
            model_name='margemlivre',
            name='collateral_key',
            field=models.CharField(
                blank=True, max_length=200, null=True, verbose_name='Collateral_Key'
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='document_key_QiTech_CCB',
            field=models.CharField(
                blank=True,
                max_length=200,
                null=True,
                verbose_name='Chave do Documento CCB',
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='dt_envio_proposta_CIP',
            field=models.DateField(
                blank=True,
                help_text='Data de envio do aceite da proposta para a CIP',
                null=True,
                verbose_name='Data de envio da proposta(CIP)',
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='dt_liberado_cliente',
            field=models.DateTimeField(
                default='2023-09-20 12:00:00',
                verbose_name='Data de liberação do cliente',
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='dt_vencimento_primeira_parcela',
            field=models.DateField(
                default='2023-09-20',
                verbose_name='Data de vencimento da primeira parcela',
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='dt_vencimento_ultima_parcela',
            field=models.DateField(
                default='2023-12-31',
                verbose_name='Data de vencimento da última parcela',
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='fl_seguro',
            field=models.BooleanField(default=False, verbose_name='Seguro?'),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='related_party_key',
            field=models.CharField(
                blank=True, max_length=200, null=True, verbose_name='Related_Party_Key'
            ),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='vr_seguro',
            field=models.IntegerField(default=0, verbose_name='Valor do Seguro'),
        ),
        migrations.AddField(
            model_name='margemlivre',
            name='vr_tarifa_cadastro',
            field=models.IntegerField(
                default=0, verbose_name='Valor da tarifa de cadastro'
            ),
        ),
    ]
