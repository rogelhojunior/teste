from contract.constants import (
    EnumArquivosSeguros,
    EnumContratoStatus,
    EnumSeguradoras,
    EnumStatus,
    EnumTipoAnexo,
    EnumTipoComunicacao,
    EnumTipoContrato,
    EnumTipoMargem,
    EnumTipoPlano,
    EnumTipoProduto,
    NomeAverbadoras,
    SiapeLinkTypeEnum,
    EnumStatusCancelamento,
    EnumTipoPendencia,
    EnumEscolaridade,
    EnumGrauParentesco,
)

TIPOS_PRODUTO = (
    (EnumTipoProduto.FGTS, 'FGTS'),
    (EnumTipoProduto.INSS_REPRESENTANTE_LEGAL, 'INSS - Representante Legal'),
    (
        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        'Cartão Benefício - Representante Legal',
    ),
    (EnumTipoProduto.PAB, 'PAB'),
    (EnumTipoProduto.INSS_CORBAN, 'INSS CORBAN'),
    (EnumTipoProduto.INSS, 'INSS'),
    (EnumTipoProduto.CARTAO_BENEFICIO, 'Cartão Benefício'),
    (EnumTipoProduto.SIAPE, 'Siape'),
    (EnumTipoProduto.EXERCITO, 'Exercito'),
    (EnumTipoProduto.MARINHA, 'Marinha'),
    (EnumTipoProduto.AERONAUTICA, 'Aeronautica'),
    (EnumTipoProduto.PORTABILIDADE, 'Portabilidade'),
    (EnumTipoProduto.CONSIGNADO, 'Consignado'),
    (EnumTipoProduto.SAQUE_COMPLEMENTAR, 'Saque Complementar'),
    (EnumTipoProduto.CARTAO_CONSIGNADO, 'Cartão Consignado'),
    (EnumTipoProduto.MARGEM_LIVRE, 'Margem Livre'),
    (EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO, 'Portabilidade + Refinanciamento'),
)

TIPOS_PRODUTO_REGRA_IDADE = (
    (EnumTipoProduto.CARTAO_BENEFICIO, 'Cartão Benefício'),
    (EnumTipoProduto.CARTAO_CONSIGNADO, 'Cartão Consignado'),
)


TIPOS_STATUS = (
    (EnumStatus.EMPTY, ''),
    (EnumStatus.CRIADO_COM_SUCESSO, 'Criado com sucesso'),
    (
        EnumStatus.RECUSADO_ERRO_NECESSITA_DE_ATENCAO,
        'Recusado Erro - Necessita de Atenção',
    ),
    (EnumStatus.RECUSADO_PELA_OPERADORA, 'Recusado pela Operadora'),
    (EnumStatus.CANCELADO, 'Cancelado'),
)

TIPOS_CANCELMENTO = (
    (EnumStatusCancelamento.CANCELAMENTO_PEDIDO, 'Cancelamento a pedido'),
    (
        EnumStatusCancelamento.CANCELAMENTO_INADIMPLENCIA,
        'Cancelamento por inadimplência',
    ),
    (EnumStatusCancelamento.CANCELAMENTO_SINISTRO, 'Cancelamento por sinistro'),
    (EnumStatusCancelamento.CANCELAMENTO_TROCA, 'Por troca de plano'),
)


TIPOS_CONTRATO = (
    (EnumTipoContrato.OPERACAO_NOVA, 'Operação nova (margem livre)'),
    (EnumTipoContrato.REFINANCIAMENTO, 'Refinanciamento'),
    (EnumTipoContrato.REFIN_PORTABILIDADE, 'Refin Portabilidade'),
    (EnumTipoContrato.PORTABILIDADE, 'Portabilidade'),
    (EnumTipoContrato.NOVO_AUMENTO_SALARIAL, 'Novo Aumento Salarial'),
    (EnumTipoContrato.SAQUE_COMPLEMENTAR, 'Saque Complementar'),
)

TIPOS_ANEXO = (
    (EnumTipoAnexo.CCB, 'CCB'),
    (EnumTipoAnexo.DOCUMENTO_FRENTE, 'Documento do cliente frente'),
    (EnumTipoAnexo.DOCUMENTO_VERSO, 'Documento do cliente verso'),
    (EnumTipoAnexo.DOCUMENTOS_ADICIONAIS, 'Documentos Adicionais'),
    (EnumTipoAnexo.SELFIE, 'Selfie'),
    (EnumTipoAnexo.FOTO_PROVA_VIDA, 'Foto da Prova de Vida'),
    (EnumTipoAnexo.COMPROVANTE_ENDERECO, 'Comprovante de endereço'),
    (EnumTipoAnexo.COMPROVANTE_FINANCEIRO, 'Comprovante financeiro'),
    (EnumTipoAnexo.REPASSE, 'Repasse'),
    (EnumTipoAnexo.ARQUIVO_RETORNO_RESERVA, 'Arquivo retorno reserva'),
    (EnumTipoAnexo.CNH, 'Documento - CNH'),
    (EnumTipoAnexo.FRENTE_CNH, 'Documento Frente - CNH'),
    (EnumTipoAnexo.VERSO_CNH, 'Documento Verso - CNH'),
    (EnumTipoAnexo.TERMOS_E_ASSINATURAS, 'Termos e assinaturas'),
    (EnumTipoAnexo.CONTRACHEQUE, 'Contracheque'),
    (EnumTipoAnexo.DOCUMENTO_ASSINADO_FISICAMENTE, 'Documento assinado fisicamente'),
    (EnumTipoAnexo.DOCUMENTO_FRENTE_ROGADO, 'Documento frente rogado'),
    (EnumTipoAnexo.DOCUMENTO_VERSO_ROGADO, 'Documento verso rogado'),
    (EnumTipoAnexo.CNH_ROGADO, 'CNH rogado'),
    (EnumTipoAnexo.DOCUMENTO_FRENTE_TESTEMUNHA, 'Documento frente testemunha'),
    (EnumTipoAnexo.DOCUMENTO_VERSO_TESTEMUNHA, 'Documento verso testemunha'),
    (EnumTipoAnexo.CNH_TESTEMUNHA, 'CNH testemunha'),
)

TIPOS_PENDENCIA = (
    (EnumTipoPendencia.SENHA_DE_AVERBACAO, 'Senha de averbação'),
    (EnumTipoPendencia.CONTRACHEQUE, 'Contracheque'),
    (EnumTipoPendencia.DEMAIS_ANEXOS_DE_AVERBACAO, 'Demais anexos de averbação'),
)

CONTRATO_STATUS = (
    (EnumContratoStatus.DIGITACAO, 'Digitação'),
    (EnumContratoStatus.AGUARDANDO_FORMALIZACAO, 'Aguardando Formalização'),
    (EnumContratoStatus.FORMALIZADO, 'Formalizado'),
    (EnumContratoStatus.MESA, 'Mesa'),
    (EnumContratoStatus.EM_AVERBACAO, 'Em Averbação'),
    (EnumContratoStatus.PAGO, 'Pago'),
    (EnumContratoStatus.CANCELADO, 'Cancelado'),
)

AVERBADORAS = (
    (NomeAverbadoras.FACIL.value, 'Facil'),
    (NomeAverbadoras.ZETRASOFT.value, 'Zetrasoft'),
    (NomeAverbadoras.QUANTUM.value, 'Quantum'),
    (NomeAverbadoras.DATAPREV_BRB.value, 'Dataprev - BRB'),
    (NomeAverbadoras.DATAPREV_PINE.value, 'Dataprev - PINE'),
    (NomeAverbadoras.SERPRO.value, 'Serpro'),
    (NomeAverbadoras.NEOCONSIG.value, 'Neoconsig'),
)

TIPOS_COMUNICACAO = (
    (EnumTipoComunicacao.ARQUIVO, 'Arquivo'),
    (EnumTipoComunicacao.API, 'API'),
)

SEGURADORAS = (
    (EnumSeguradoras.TEM_SAUDE, 'Tem Saúde'),
    (EnumSeguradoras.GENERALI, 'Generali'),
    (EnumSeguradoras.SABEMI, 'Sabemi'),
)

TIPOS_PLANO = (
    (EnumTipoPlano.PRATA, 'Prata'),
    (EnumTipoPlano.OURO, 'Ouro'),
    (EnumTipoPlano.DIAMANTE, 'Diamante'),
)


TIPOS_MARGEM = (
    (EnumTipoMargem.MARGEM_COMPRA, 'Margem Compra'),
    (EnumTipoMargem.MARGEM_SAQUE, 'Margem Saque'),
    (EnumTipoMargem.MARGEM_UNICA, 'Margem Unica'),
    (EnumTipoMargem.MARGEM_UNIFICADA, 'Margem Unificada'),
)

TIPO_VINCULO_SIAPE: tuple[tuple[int, str]] = tuple(
    (member.value, member.name.capitalize()) for member in SiapeLinkTypeEnum
)


TIPOS_ARQUVIOS = (
    (EnumArquivosSeguros.VIDA_SIAPE.value, 'Termo Vida - Siape'),
    (EnumArquivosSeguros.VIDA_INSS.value, 'Termo Vida - INSS'),
    (EnumArquivosSeguros.OURO_INSS.value, 'Termo Ouro - INSS'),
    (EnumArquivosSeguros.DIAMANTE_INSS.value, 'Termo Diamanete - INSS'),
    (EnumArquivosSeguros.OURO_DEMAIS_CONVENIOS.value, 'Termo Ouro - Demais Convênios'),
    (
        EnumArquivosSeguros.DIAMANTE_DEMAIS_CONVENIOS.value,
        'Termo Diamante - Demais Convênios',
    ),
)

ESCOLARIDADE = (
    (EnumEscolaridade.ENSINO_FUNDAMENTAL, 'Ensino Fundamental'),
    (EnumEscolaridade.ENSINO_MEDIO, 'Ensino Médio'),
    (EnumEscolaridade.ENSINO_SUPERIOR, 'Ensino Superior'),
    (EnumEscolaridade.POS_GRADUADO, 'Pós Graduado'),
    (EnumEscolaridade.ANALFABETO, 'Analfabeto'),
)

GRAU_PARENTESCO = (
    (EnumGrauParentesco.PAI, 'Pai'),
    (EnumGrauParentesco.MAE, 'Mãe'),
    (EnumGrauParentesco.FILHO, 'Filho'),
    (EnumGrauParentesco.CONJUGE, 'Cônjuge'),
    (EnumGrauParentesco.IRMAO, 'Irmão'),
)
