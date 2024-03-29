# Generated by Django 4.2.3 on 2023-10-20 15:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_dadosbancarios_updated_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricoAceiteIN100',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.IntegerField(choices=[(1, 'Autoatendimento'), (2, 'Agencia'), (3, 'Digital Via Cliente'), (4, 'Digital Via Correspondente'), (5, 'Mobile')], default=4, verbose_name='Canal')),
                ('hash_assinatura', models.CharField(max_length=100, null=True, verbose_name='Hash da Assinatura')),
                ('data_aceite', models.DateField(blank=True, null=True, verbose_name='Data aceite')),
                ('data_vencimento_aceite', models.DateField(null=True, verbose_name='Data de vencimento do aceite')),
                ('produto', models.SmallIntegerField(choices=[(1, 'FGTS'), (2, 'INSS - Representante Legal'), (3, 'Cartão Benefício - Representante Legal'), (4, 'PAB'), (5, 'INSS CORBAN'), (6, 'INSS'), (7, 'Cartão Benefício'), (8, 'Siape'), (9, 'Exercito'), (10, 'Marinha'), (11, 'Aeronautica'), (12, 'Portabilidade'), (13, 'Consignado'), (14, 'Saque Complementar'), (15, 'Cartão Consignado'), (16, 'Margem Livre')], default=7, verbose_name='Tipo de Produto')),
                ('aceite_original', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.aceitein100', verbose_name='Aceite Original')),
            ],
            options={
                'verbose_name': 'Histórico de Aceite',
                'verbose_name_plural': 'Históricos de Aceite',
            },
        ),
        migrations.CreateModel(
            name='DadosBeneficioIN100',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_beneficio', models.CharField(max_length=100, null=True, verbose_name='Numero Benefício')),
                ('cpf', models.CharField(max_length=11, null=True, verbose_name='CPF')),
                ('nome_beneficiario', models.CharField(max_length=255, null=True, verbose_name='Nome Beneficiario')),
                ('codigo_situacao_beneficio', models.IntegerField(null=True, verbose_name='Código Situação Benefício')),
                ('descricao_situacao_beneficio', models.CharField(max_length=255, null=True, verbose_name='Descrição Situação Benefício')),
                ('codigo_especie_beneficio', models.IntegerField(null=True, verbose_name='Código Espécie Benefício')),
                ('descricao_especie_beneficio', models.CharField(max_length=255, null=True, verbose_name='Descrição Espécie Benefício')),
                ('concessao_judicial', models.BooleanField(verbose_name='Concessão Judicial')),
                ('uf_pagamento', models.CharField(max_length=2, null=True, verbose_name='UF Pagamento')),
                ('codigo_tipo_credito', models.IntegerField(null=True, verbose_name='Código Tipo Crédito')),
                ('descricao_tipo_credito', models.CharField(max_length=255, null=True, verbose_name='Descrição Tipo Crédito')),
                ('cbc_if_pagadora', models.IntegerField(null=True, verbose_name='CBC IF Pagadora')),
                ('agencia_pagadora', models.IntegerField(null=True, verbose_name='Agência Pagadora')),
                ('conta_corrente', models.CharField(max_length=20, null=True, verbose_name='Conta Corrente')),
                ('possui_representante_legal', models.BooleanField(verbose_name='Possui Representante Legal')),
                ('possui_procurador', models.BooleanField(verbose_name='Possui Procurador')),
                ('possui_entidade_representacao', models.BooleanField(verbose_name='Possui Entidade Representação')),
                ('codigo_pensao_alimenticia', models.IntegerField(null=True, verbose_name='Código Pensão Alimentícia')),
                ('descricao_pensao_alimenticia', models.CharField(max_length=255, null=True, verbose_name='Descrição Pensão Alimentícia')),
                ('bloqueado_para_emprestimo', models.BooleanField(verbose_name='Bloqueado Para Empréstimo')),
                ('margem_disponivel', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Margem Disponível')),
                ('margem_disponivel_cartao', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Margem Disponível Cartão')),
                ('valor_limite_cartao', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Limite Cartão')),
                ('qtd_emprestimos_ativos_suspensos', models.IntegerField(verbose_name='Qtd. Empréstimos Ativos Suspensos')),
                ('qtd_emprestimos_ativos', models.IntegerField(verbose_name='Qtd. Empréstimos Ativos')),
                ('qtd_emprestimos_suspensos', models.IntegerField(verbose_name='Qtd. Empréstimos Suspensos')),
                ('qtd_emprestimos_refin', models.IntegerField(verbose_name='Qtd. Empréstimos Refin')),
                ('qtd_emprestimos_porta', models.IntegerField(verbose_name='Qtd. Empréstimos Porta')),
                ('data_consulta', models.DateField(verbose_name='Data Consulta')),
                ('elegivel_emprestimo', models.BooleanField(verbose_name='Elegível Empréstimo')),
                ('margem_disponivel_rcc', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Margem Disponível RCC')),
                ('valor_limite_rcc', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Limite RCC')),
                ('valor_liquido', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Líquido')),
                ('valor_comprometido', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Comprometido')),
                ('valor_maximo_comprometimento', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor Máximo Comprometimento')),
                ('aceite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.aceitein100', verbose_name='Aceite')),
            ],
            options={
                'verbose_name': 'Dado Benefício',
                'verbose_name_plural': 'Dados Benefício',
            },
        ),
    ]
