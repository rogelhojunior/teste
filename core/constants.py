class EnumTipoConta(object):
    CORRENTE_PESSOA_FISICA = 1
    CORRENTE_PESSOA_JURIDICA = 2
    POUPANCA_PESSOA_FISICA = 3
    CARTAO_MAGNETICO = 4
    CONTA_PAGAMENTO_PESSOA_FISICA = 5


class EnumEstadoCivil(object):
    SOLTEIRO = 1
    CASADO = 2
    SEPARADO = 3
    DIVORCIADO = 4
    VIUVO = 5


class EnumUF(object):
    AC = 1
    AL = 2
    AP = 3
    AM = 4
    BA = 5
    CE = 6
    DF = 7
    ES = 8
    GO = 9
    MA = 10
    MT = 11
    MS = 12
    MG = 13
    PA = 14
    PB = 15
    PR = 16
    PE = 17
    PI = 18
    RJ = 19
    RN = 20
    RS = 21
    RO = 22
    RR = 23
    SC = 24
    SP = 25
    SE = 26
    TO = 27


class EnumTipoCliente(object):
    CLIENTE = 1
    REPRESENTANTE_LEGAL = 2


class EnumTipoResidencia(object):
    PROPRIA = 1
    ALUGADA = 2
    FAMILIARES = 3
    EMPRESA = 4


class EnumTipoPagamento(object):
    TED = 1
    PIX = 2


class EnumTipoContrato(object):
    OPERACAO_NOVA = 1
    REFINANCIAMENTO = 2
    REFIN_PORTABILIDADE = 3
    PORTABILIDADE = 4
    NOVO_AUMENTO_SALARIAL = 5


class EnumTipoDocumento(object):
    RG = 1
    CNH = 2


class EnumSexo(object):
    FEMININO = 1
    MASCULINO = 2


class EnumAcaoCorban(object):
    APROVAR = 1
    RECUSAR = 2
    PENDENCIAR = 3


class EnumCargo(object):
    AGENTE = 1
    GERENTE = 2
    SUPERINTENDENTE = 3


class EnumAtuacao(object):
    REGIONAL = 1
    DISTRITAL = 2


class EnumRegiao(object):
    BLANK = 0
    NORTE = 1
    NORDESTE = 2
    CENTRO_OESTE = 3
    SUL = 4
    SUDESTE = 5


class EnumEstabelecimento(object):
    VIRTUAL = 1
    FISICO = 2


class EnumVenda(object):
    B2C = 1  # Direto ao cliente
    B2B2C = 2  # Comercial


class EnumCadastro(object):
    MATRIZ = 1
    SUBSIDIARIA = 2
    SUBESTABELECIMENTO = 3


class EnumRelacionamento(object):
    PROPRIETARIO = 1
    REPRESENTANTE_LEGAL = 2
    REPRESENTANTE_AUTORIZADO = 3


class EnumCanalAutorizacaoDigital(object):
    AUTOATENDIMENTO = 1
    AGENCIA = 2
    DIGITAL_VIA_CLIENTE = 3
    DIGITAL_VIA_CORRESPONDENTE = 4
    MOBILE = 5


class EnumGrauCorban(object):
    CORBAN_MASTER = 1
    SUBESTABELECIDO = 2
    LOJA = 3
    FILIAL = 4


class EnumNivelHierarquia(object):
    ADMINISTRADOR = 5
    DONO_LOJA = 4
    GERENTE = 3
    SUPERVISOR = 2
    DIGITADOR = 1
