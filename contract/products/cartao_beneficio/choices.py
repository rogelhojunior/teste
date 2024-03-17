from contract.products.cartao_beneficio.constants import ContractStatus, SeguroStatus

STATUS_NAME = (
    # CARTAO_BENEFICIO
    (ContractStatus.ANDAMENTO_SIMULACAO.value, 'Simulação'),
    (ContractStatus.ANDAMENTO_FORMALIZACAO.value, 'Formalizaçao (cliente)'),
    (ContractStatus.APROVADA_FINALIZADA.value, 'Aprovada – Finalizada'),
    (ContractStatus.REPROVADA_FINALIZADA.value, 'Reprovada – Finalizada'),
    (ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value, 'Checagem – Mesa Formalização'),
    (ContractStatus.APROVADA_MESA_FORMALIZACAO.value, 'Aprovada – Mesa Formalização'),
    (ContractStatus.REPROVADA_MESA_FORMALIZACAO.value, 'Reprovada – Finalizada'),
    (ContractStatus.PENDENTE_DOCUMENTACAO.value, 'Pendente Documentação'),
    (ContractStatus.EM_AVERBACAO.value, 'Em averbação'),
    (ContractStatus.APROVADA_AVERBACAO.value, 'Aprovada - Averbação'),
    (ContractStatus.RECUSADA_AVERBACAO.value, 'Recusada - Averbação'),
    (ContractStatus.ANDAMENTO_EMISSAO_CARTAO.value, 'Andamento – Emissão cartão'),
    (ContractStatus.FINALIZADA_EMISSAO_CARTAO.value, 'Finalizada – Emissão cartão'),
    (
        ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
        'Andamento – Liberação Pagamento Saque',
    ),
    (
        ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
        'Finalizado – Liberação Pagamento Saque',
    ),
    (
        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
        'Pendente - Correção de dados bancários',
    ),
    (ContractStatus.ERRO_SOLICITACAO_SAQUE.value, 'Erro - Transmissão do Contrato'),
    (ContractStatus.ERRO_CRIACAO_CARTAO.value, 'Erro - Criação do Cartão'),
    # PORTABILIDADE
    (ContractStatus.AGUARDA_ENVIO_LINK.value, 'Aguarda envio link'),
    (ContractStatus.FORMALIZACAO_CLIENTE.value, 'Formalização (cliente)'),
    (ContractStatus.ANALISE_DE_CREDITO.value, 'Análise de crédito (Bureaus)'),
    (ContractStatus.PENDENTE_DADOS_DIVERGENTES.value, 'Pendente - Dados Divergentes'),
    (ContractStatus.REPROVADA_POLITICA_INTERNA.value, 'Reprovada – Política Interna'),
    (ContractStatus.CHECAGEM_MESA_CORBAN.value, 'Checagem - Mesa Corban'),
    (
        ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value,
        'Pendente Documentação - Mesa Corban',
    ),
    (ContractStatus.REPROVADA_MESA_CORBAN.value, 'Reprovada – Mesa Corban'),
    (ContractStatus.APROVADA_MESA_CORBAN.value, 'Aprovada - Mesa Corban'),
    (
        ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value,
        'Checagem - Mesa de Formalização',
    ),
    (
        ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
        'Aprovada - Mesa de Formalização',
    ),
    (
        ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
        'Reprovada – Mesa de Formalização',
    ),
    (
        ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
        'Checagem - Mesa de Averbaçao',
    ),
    (ContractStatus.AGUARDA_RETORNO_SALDO.value, 'Aguarda Retorno Saldo'),
    (ContractStatus.SALDO_RETORNADO.value, 'Saldo Retornado'),
    (ContractStatus.INT_CONFIRMA_PAGAMENTO.value, 'INT - Confirma pagamento'),
    (ContractStatus.SALDO_REPROVADO.value, 'Saldo Reprovado'),
    (
        ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
        'Reprovada - Pagamento Devolvido',
    ),
    (ContractStatus.INT_AGUARDA_AVERBACAO.value, 'Int - Aguarda Averbação'),
    (ContractStatus.INT_FINALIZADO.value, 'Int - Finalizado'),
    (
        ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value,
        'Int - Aguardando Desembolso do Refinanciamento',
    ),
    (ContractStatus.INT_AVERBACAO_PENDENTE.value, 'Int - Averbação Pendente'),
    (ContractStatus.REPROVADO.value, 'Reprovado'),
    (ContractStatus.AGUARDANDO_RETORNO_IN100.value, 'Aguardando Retorno da IN100'),
    (
        ContractStatus.AGUARDANDO_IN100_RECALCULO.value,
        'Aguardando Consulta IN100 (RECALCULO)',
    ),
    (
        ContractStatus.RETORNO_IN100_RECALCULO_RECEBIDO.value,
        'IN100 Consultada no Recalculo',
    ),
    (
        ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value,
        'Pendente - Aprovação do Recalculo (Corban)',
    ),
    (
        ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
        'Revisão - Mesa de Formalização',
    ),
    (
        ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
        'Reprovada Revisão - Mesa de Formalização',
    ),
    (
        ContractStatus.AVERBACAO_MESA_DE_FORMALIZACAO.value,
        'Averbação - Mesa de Formalização',
    ),
    (
        ContractStatus.SAQUE_CANCELADO_LIMITE_DISPONIVEL_INSUFICIENTE.value,
        'Saque Cancelado - Limite disponível Insuficiente',
    ),
    (
        ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
        'Saque Recusado - Problema no Pagamento',
    ),
    (
        ContractStatus.ANDAMENTO_REAPRESENTACAO_DO_PAGAMENTO_DE_SAQUE.value,
        'Andamento - Reapresentação do pagamento de saque',
    ),
    (
        ContractStatus.PENDENCIADO.value,
        'Pendenciado',
    ),
    (
        ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV.value,
        'Em Andamento – Consulta Dataprev',
    ),
    (
        ContractStatus.ERRO_CONSULTA_DATAPREV.value,
        'Erro – Consulta Dataprev',
    ),
    (
        ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
        'Reprovado – Consulta Dataprev',
    ),
    (
        ContractStatus.AGUARDANDO_AVERBACAO_REFIN.value,
        'Aguardando Averbação Refinanciamento',
    ),
    (
        ContractStatus.AGUARDANDO_FINALIZAR_PORT.value,
        'Aguardando Finalizar PORT',
    ),
    (
        ContractStatus.INT_FINALIZADO_DO_REFIN.value,
        'Int - Finalizado Refin',
    ),
    (
        ContractStatus.AGUARDA_FINALIZACAO_PROPOSTA_PRINCIPAL.value,
        'Ag. finalização proposta principal',
    ),
    (
        ContractStatus.INT_AJUSTE_AVERBACAO.value,
        'Int - Ajuste Averbação',
    ),
    (
        ContractStatus.REPROVADA_MESA_DE_AVERBECAO.value,
        'Reprovado - Mesa de Averbação',
    ),
    (
        ContractStatus.VALIDACOES_AUTOMATICAS.value,
        'Validações Automáticas',
    ),
    (
        ContractStatus.AGUARDANDO_DESEMBOLSO.value,
        'Aguardando Desembolso',
    ),
    (
        ContractStatus.INT_AGUARDANDO_PAGO_QITECH.value,
        'Int- Aguardando pago da QiTech',
    ),
    (
        ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value,
        'Pendencias para Averbação – Corban',
    ),
    (
        ContractStatus.REGULARIZADA_MESA_AVERBACAO.value,
        'Regularizada Averbação – Mesa de Averbação',
    ),
    (
        ContractStatus.FINALIZADA_FORMALIZACAO_CLIENTE.value,
        'Finalizada formalização do cliente',
    ),
    (
        ContractStatus.FINALIZADA_FORMALIZACAO_ROGADO.value,
        'Finalizada formalização do rogado',
    ),
)

SEGURO_STATUS = (
    (SeguroStatus.CRIADO_SUCESSO.value, 'Criado com sucesso'),
    (
        SeguroStatus.RECUSADO_ERRO_NECESSITA_ATENCAO.value,
        'Recusado Erro - Necessita de Atenção',
    ),
    (SeguroStatus.RECUSADO_OPERADORA.value, 'Recusado pela Operadora'),
)
