from core.constants import (
    EnumAtuacao,
    EnumCadastro,
    EnumCanalAutorizacaoDigital,
    EnumCargo,
    EnumEstabelecimento,
    EnumEstadoCivil,
    EnumGrauCorban,
    EnumNivelHierarquia,
    EnumRegiao,
    EnumRelacionamento,
    EnumSexo,
    EnumTipoCliente,
    EnumTipoConta,
    EnumTipoContrato,
    EnumTipoDocumento,
    EnumTipoPagamento,
    EnumTipoResidencia,
    EnumUF,
    EnumVenda,
)

TIPOS_CONTA = (
    (EnumTipoConta.CORRENTE_PESSOA_FISICA, 'Conta Corrente Pessoa Física'),
    (EnumTipoConta.CORRENTE_PESSOA_JURIDICA, 'Conta Corrente Pessoa Jurídica'),
    (EnumTipoConta.POUPANCA_PESSOA_FISICA, 'Conta Poupança Pessoa Física'),
    (EnumTipoConta.CARTAO_MAGNETICO, 'Cartão magnético'),
    (EnumTipoConta.CONTA_PAGAMENTO_PESSOA_FISICA, 'Conta Pagamento Pessoa Física'),
)

ESTADO_CIVIL = (
    (EnumEstadoCivil.SOLTEIRO, 'Solteiro(a)'),
    (EnumEstadoCivil.CASADO, 'Casado(a)'),
    (EnumEstadoCivil.SEPARADO, 'Separado(a)'),
    (EnumEstadoCivil.DIVORCIADO, 'Divorciado(a)'),
    (EnumEstadoCivil.VIUVO, 'Viúva(a)'),
)

UFS = (
    (EnumUF.AC, 'AC'),
    (EnumUF.AL, 'AL'),
    (EnumUF.AP, 'AP'),
    (EnumUF.AM, 'AM'),
    (EnumUF.BA, 'BA'),
    (EnumUF.CE, 'CE'),
    (EnumUF.DF, 'DF'),
    (EnumUF.ES, 'ES'),
    (EnumUF.GO, 'GO'),
    (EnumUF.MA, 'MA'),
    (EnumUF.MT, 'MT'),
    (EnumUF.MS, 'MS'),
    (EnumUF.MG, 'MG'),
    (EnumUF.PA, 'PA'),
    (EnumUF.PB, 'PB'),
    (EnumUF.PR, 'PR'),
    (EnumUF.PE, 'PE'),
    (EnumUF.PI, 'PI'),
    (EnumUF.RJ, 'RJ'),
    (EnumUF.RN, 'RN'),
    (EnumUF.RS, 'RS'),
    (EnumUF.RO, 'RO'),
    (EnumUF.RR, 'RR'),
    (EnumUF.SC, 'SC'),
    (EnumUF.SP, 'SP'),
    (EnumUF.SE, 'SE'),
    (EnumUF.TO, 'TO'),
)

TIPOS_CLIENTE = (
    (EnumTipoCliente.CLIENTE, 'Cliente'),
    (EnumTipoCliente.REPRESENTANTE_LEGAL, 'Representante legal'),
)

TIPOS_RESIDENCIA = (
    (EnumTipoResidencia.PROPRIA, 'Própria'),
    (EnumTipoResidencia.ALUGADA, 'Alugada'),
    (EnumTipoResidencia.FAMILIARES, 'Familiares'),
    (EnumTipoResidencia.EMPRESA, 'Empresa'),
)

TIPOS_PAGAMENTO = (
    (EnumTipoPagamento.TED, 'TED'),
    (EnumTipoPagamento.PIX, 'PIX'),
)

TIPOS_CONTRATO = (
    (EnumTipoContrato.OPERACAO_NOVA, 'Operação nova (margem livre)'),
    (EnumTipoContrato.REFINANCIAMENTO, 'Refinanciamento'),
    (EnumTipoContrato.REFIN_PORTABILIDADE, 'Refin Portabilidade'),
    (EnumTipoContrato.PORTABILIDADE, 'Portabilidade'),
    (EnumTipoContrato.NOVO_AUMENTO_SALARIAL, 'Novo Aumento Salarial'),
)

TIPOS_DOCUMENTO = (
    (EnumTipoDocumento.RG, 'RG'),
    (EnumTipoDocumento.CNH, 'CNH'),
)

TIPOS_SEXO = (
    (EnumSexo.FEMININO, 'Feminino'),
    (EnumSexo.MASCULINO, 'Masculino'),
)

CARGO = (
    (EnumCargo.AGENTE, 'Agente'),
    (EnumCargo.GERENTE, 'Gerente'),
    (EnumCargo.SUPERINTENDENTE, 'Superintendente'),
)

TIPOS_ATUACAO = (
    (EnumAtuacao.REGIONAL, 'Regional'),
    (EnumAtuacao.DISTRITAL, 'Distrital'),
)

TIPOS_REGIAO = (
    (EnumRegiao.NORTE, 'Norte'),
    (EnumRegiao.NORDESTE, 'Nordeste'),
    (EnumRegiao.CENTRO_OESTE, 'Centro-Oeste'),
    (EnumRegiao.SUL, 'Sul'),
    (EnumRegiao.SUDESTE, 'Sudeste'),
    (EnumRegiao.BLANK, '-------'),
)

TIPOS_ESTABELECIMENTO = (
    (EnumEstabelecimento.VIRTUAL, 'Virtual'),
    (EnumEstabelecimento.FISICO, 'Físico'),
)

TIPOS_VENDA = (
    (EnumVenda.B2C, 'B2C - Direto ao Cliente'),
    (EnumVenda.B2B2C, 'B2B2C - Comercial'),
)

TIPOS_CADASTRO = (
    (EnumCadastro.MATRIZ, 'Matriz'),
    (EnumCadastro.SUBSIDIARIA, 'Subsidiária'),
    (EnumCadastro.SUBESTABELECIMENTO, 'Subestabelecimento'),
)

TIPOS_RELACIONAMENTO = (
    (EnumRelacionamento.PROPRIETARIO, 'Proprietário'),
    (EnumRelacionamento.REPRESENTANTE_LEGAL, 'Representante Legal'),
    (EnumRelacionamento.REPRESENTANTE_AUTORIZADO, 'Representante Autorizado'),
)

CANAL_AUTORIZACAO_DIGITAL = (
    (EnumCanalAutorizacaoDigital.AUTOATENDIMENTO, 'Autoatendimento'),
    (EnumCanalAutorizacaoDigital.AGENCIA, 'Agencia'),
    (EnumCanalAutorizacaoDigital.DIGITAL_VIA_CLIENTE, 'Digital Via Cliente'),
    (
        EnumCanalAutorizacaoDigital.DIGITAL_VIA_CORRESPONDENTE,
        'Digital Via Correspondente',
    ),
    (EnumCanalAutorizacaoDigital.MOBILE, 'Mobile'),
)

GRAU_CORBAN = (
    (EnumGrauCorban.CORBAN_MASTER, 'Corban Master'),
    (EnumGrauCorban.SUBESTABELECIDO, 'Substabelecido'),
    (EnumGrauCorban.LOJA, 'Loja'),
    (EnumGrauCorban.FILIAL, 'Filial'),
)


NIVEIS_HIERARQUIA = (
    (EnumNivelHierarquia.ADMINISTRADOR, 'Administrador'),
    (EnumNivelHierarquia.DONO_LOJA, 'Dono da Loja'),
    (EnumNivelHierarquia.GERENTE, 'Gerente'),
    (EnumNivelHierarquia.SUPERVISOR, 'Supervisor'),
    (EnumNivelHierarquia.DIGITADOR, 'Digitador'),
)
