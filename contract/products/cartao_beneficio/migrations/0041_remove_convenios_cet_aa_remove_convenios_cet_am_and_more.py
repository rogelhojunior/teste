# Generated by Django 4.2.3 on 2023-11-03 14:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cartao_beneficio', '0040_convenios_idade_minima_assinatura_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='convenios',
            name='cet_aa',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='cet_am',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='corte',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='data_vencimento_fatura',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='fator',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='id_imagem_dock',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='id_plastico_dock',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='id_produto_logo_dock',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='idade_maxima',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='idade_minima',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='limite_maximo_credito',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='limite_minimo_credito',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='margem_maxima',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='margem_minima',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='percentual_saque',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='permite_saque',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='permite_saque_parcelado',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='porcentagem_seguro',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='produto',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='saque_parc_cod_dock',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='saque_parc_qnt_min_parcelas',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='saque_parc_val_min',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='saque_parc_val_total',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='seguro_obrigatorio',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='taxa_produto',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='verba',
        ),
        migrations.RemoveField(
            model_name='convenios',
            name='vr_minimo_saque',
        ),
        migrations.AlterField(
            model_name='seguros',
            name='produto',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Saque Complementar'), (15, 'Cartão Consignado'), (16, 'Margem Livre'), (17, 'Portabilidade + Refinanciamento')], null=True, verbose_name='Produtos para a oferta'),
        ),
        migrations.CreateModel(
            name='ProdutoConvenio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('produto', models.SmallIntegerField(blank=True, choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Saque Complementar'), (15, 'Cartão Consignado'), (16, 'Margem Livre'), (17, 'Portabilidade + Refinanciamento')], null=True, verbose_name='Produtos para a oferta')),
                ('margem_compra', models.BooleanField(default=False, verbose_name='Margem Compra?')),
                ('margem_saque', models.BooleanField(default=False, verbose_name='Margem Saque?')),
                ('margem_unificada', models.BooleanField(default=False, verbose_name='Margem Unificada?')),
                ('idade_minima', models.IntegerField(default=0, verbose_name='Idade mínima')),
                ('idade_maxima', models.IntegerField(default=100, verbose_name='Idade máxima')),
                ('margem_minima', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Margem mínima')),
                ('margem_maxima', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Margem máxima')),
                ('limite_minimo_credito', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Limite mínimo de crédito')),
                ('limite_maximo_credito', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Limite máximo de crédito')),
                ('fator', models.DecimalField(decimal_places=7, default=0, max_digits=12, verbose_name='Fator de multiplicação')),
                ('taxa_produto', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor da Taxa do produto')),
                ('cet_am', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Taxa CET a.m')),
                ('cet_aa', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Taxa CET a.a')),
                ('data_vencimento_fatura', models.IntegerField(blank=True, null=True, verbose_name='Dia de vencimento da fatura')),
                ('corte', models.IntegerField(blank=True, null=True, verbose_name='Dia de corte da fatura')),
                ('id_produto_logo_dock', models.IntegerField(blank=True, null=True, verbose_name='id_produto/Logo Dock')),
                ('id_plastico_dock', models.IntegerField(blank=True, null=True, verbose_name='Id Plastico')),
                ('id_imagem_dock', models.IntegerField(blank=True, null=True, verbose_name='Id Imagem')),
                ('saque_parc_cod_dock', models.IntegerField(blank=True, null=True, verbose_name='Código Dock de Lançamento do Saque Parcelado')),
                ('cartao_virtual', models.BooleanField(default=False, verbose_name='Substituir a criação do cartão físico para o cartão virtual?')),
                ('percentual_saque', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=5, null=True, verbose_name='Percentual do limite para o Saque Rotativo e/ou Parcelado')),
                ('permite_saque', models.BooleanField(default=True, null=True, verbose_name='Permite contratação de Saque Rotativo')),
                ('vr_minimo_saque', models.DecimalField(blank=True, decimal_places=7, default=0, max_digits=12, null=True, verbose_name='Valor mínimo para solicitação do Saque Rotativo')),
                ('permite_saque_parcelado', models.BooleanField(default=True, null=True, verbose_name='Permite contratação de Saque Parcelado')),
                ('saque_parc_val_min', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Valor mínimo em reais da parcela')),
                ('saque_parc_qnt_min_parcelas', models.IntegerField(blank=True, null=True, verbose_name='Quantidade mínima de parcelas')),
                ('saque_parc_val_total', models.IntegerField(blank=True, help_text='Este campo será preenchido ao final do cadastro.', null=True, verbose_name='Valor total da contratação mínimo em reais (Sem o cálculo CET)')),
                ('convenio', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='produto_convenio', to='cartao_beneficio.convenios', verbose_name='Convênio')),
            ],
            options={
                'verbose_name': 'Produto',
                'verbose_name_plural': 'Produtos',
            },
        ),
    ]
