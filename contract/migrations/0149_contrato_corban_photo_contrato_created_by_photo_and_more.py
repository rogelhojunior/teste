# Generated by Django 4.2.3 on 2023-12-28 20:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0148_anexocontrato_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrato',
            name='corban_photo',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Corban'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='created_by_photo',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Digitado por'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='is_main_proposal',
            field=models.BooleanField(blank=True, default=True, null=True, verbose_name='Proposta principal do envelope?'),
        ),
        migrations.AddField(
            model_name='portabilidade',
            name='numero_parcelas_atrasadas',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número de parcelas atrasadas'),
        ),
        migrations.AlterField(
            model_name='cartaobeneficio',
            name='status',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Status do Contrato'),
        ),
        migrations.AlterField(
            model_name='margemlivre',
            name='status',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Status do Contrato'),
        ),
        migrations.AlterField(
            model_name='portabilidade',
            name='status',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Status do Contrato'),
        ),
        migrations.AlterField(
            model_name='refinanciamento',
            name='status',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Status do Contrato'),
        ),
        migrations.AlterField(
            model_name='saquecomplementar',
            name='status',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Status do contrato'),
        ),
        migrations.AlterField(
            model_name='statuscontrato',
            name='nome',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Simulação'), (5, 'Formalizaçao (cliente)'), (6, 'Aprovada – Finalizada'), (7, 'Reprovada – Finalizada'), (8, 'Checagem – Mesa Formalização'), (9, 'Aprovada – Mesa Formalização'), (10, 'Reprovada – Finalizada'), (11, 'Pendente Documentação'), (12, 'Em averbação'), (13, 'Aprovada - Averbação'), (14, 'Recusada - Averbação'), (15, 'Andamento – Emissão cartão'), (16, 'Finalizada – Emissão cartão'), (17, 'Andamento – Liberação Pagamento Saque'), (18, 'Finalizado – Liberação Pagamento Saque'), (19, 'Pendente - Correção de dados bancários'), (40, 'Erro - Transmissão do Contrato'), (59, 'Erro - Criação do Cartão'), (20, 'Aguarda envio link'), (21, 'Formalização (cliente)'), (22, 'Análise de crédito (Bureaus)'), (23, 'Pendente - Dados Divergentes'), (24, 'Reprovada – Política Interna'), (25, 'Checagem - Mesa Corban'), (26, 'Pendente Documentação - Mesa Corban'), (27, 'Reprovada – Mesa Corban'), (28, 'Aprovada - Mesa Corban'), (29, 'Checagem - Mesa de Formalização'), (30, 'Aprovada - Mesa de Formalização'), (31, 'Reprovada – Mesa de Formalização'), (61, 'Checagem - Mesa de Averbaçao'), (32, 'Aguarda Retorno Saldo'), (33, 'Saldo Retornado'), (34, 'INT - Confirma pagamento'), (35, 'Saldo Reprovado'), (36, 'Reprovada - Pagamento Devolvido'), (37, 'Int - Aguarda Averbação'), (38, 'Int - Finalizado'), (56, 'Int - Aguardando Desembolso do Refinanciamento'), (39, 'Int - Averbação Pendente'), (41, 'Reprovado'), (42, 'Aguardando Retorno da IN100'), (43, 'Aguardando Consulta IN100 (RECALCULO)'), (44, 'IN100 Consultada no Recalculo'), (60, 'Pendente - Aprovação do Recalculo (Corban)'), (45, 'Revisão - Mesa de Formalização'), (46, 'Reprovada Revisão - Mesa de Formalização'), (47, 'Averbação - Mesa de Formalização'), (48, 'Saque Cancelado - Limite disponível Insuficiente'), (49, 'Saque Recusado - Problema no Pagamento'), (50, 'Andamento - Reapresentação do pagamento de saque'), (51, 'Pendenciado'), (52, 'Em Andamento – Consulta Dataprev'), (53, 'Erro – Consulta Dataprev'), (54, 'Reprovado – Consulta Dataprev'), (55, 'Aguardando Averbação Refinanciamento'), (57, 'Aguardando Finalizar PORT'), (58, 'Int - Finalizado Refin'), (62, 'Ag. finalização proposta principal')], default=1, null=True, verbose_name='Nome do status'),
        ),
    ]
