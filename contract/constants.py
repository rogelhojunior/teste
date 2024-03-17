from enum import Enum, IntEnum

from contract.products.cartao_beneficio.constants import ContractStatus


# TODO: Refatorar para poder utilizar o ProductTypeEnum
class EnumTipoProduto(object):
    FGTS = 1
    INSS_REPRESENTANTE_LEGAL = 2
    CARTAO_BENEFICIO_REPRESENTANTE = 3
    PAB = 4
    INSS_CORBAN = 5
    INSS = 6  # Sem representante
    CARTAO_BENEFICIO = 7  # Sem representante
    SIAPE = 8
    EXERCITO = 9
    MARINHA = 10
    AERONAUTICA = 11
    PORTABILIDADE = 12
    CONSIGNADO = 13
    SAQUE_COMPLEMENTAR = 14
    CARTAO_CONSIGNADO = 15
    MARGEM_LIVRE = 16
    PORTABILIDADE_REFINANCIAMENTO = 17


class ProductTypeEnum(IntEnum):
    FGTS = 1  # Fundo de Garantia do Tempo de Serviço
    INSS_LEGAL_REPRESENTATIVE = 2  # Representante Legal do INSS
    BENEFIT_CARD_REPRESENTATIVE = 3  # Representante do Cartão de Benefício
    BRAZIL_ASSISTANCE_PROGRAM = 4  # Programa Auxílio Brasil
    INSS_CORBAN = 5  # INSS processado pela Corban
    INSS_NO_REPRESENTATIVE = 6  # INSS sem representante específico
    BENEFIT_CARD = 7  # Cartão de Benefício sem representante
    SIAPE = 8  # Sistema Integrado de Administração de Recursos Humanos
    BRAZILIAN_ARMY = 9  # Exército Brasileiro
    BRAZILIAN_NAVY = 10  # Marinha do Brasil
    BRAZILIAN_AIR_FORCE = 11  # Força Aérea Brasileira
    CREDIT_PORTABILITY = 12  # Portabilidade de Crédito
    PAYROLL_LOAN = 13  # Empréstimo Consignado
    COMPLEMENTARY_WITHDRAWAL = 14  # Saque Complementar
    PAYROLL_CARD = 15  # Cartão Consignado
    FREE_MARGIN = 16  # Margem Livre
    PORTABILITY_REFINANCING = 17  # Portabilidade e Refinanciamento


class EnumStatus(object):
    EMPTY = 0
    CRIADO_COM_SUCESSO = 1
    RECUSADO_ERRO_NECESSITA_DE_ATENCAO = 2
    RECUSADO_PELA_OPERADORA = 3
    CANCELADO = 4


class EnumTipoContrato(object):
    OPERACAO_NOVA = 1
    REFINANCIAMENTO = 2
    REFIN_PORTABILIDADE = 3
    PORTABILIDADE = 4
    NOVO_AUMENTO_SALARIAL = 5
    SAQUE_COMPLEMENTAR = 6


# TODO: Atualize junto ao EnumTipoContrato até substituir-lo pelo ContractTypeEnum
class ContractTypeEnum(IntEnum):
    # TODO: Alterar para o inglês
    OPERACAO_NOVA = 1
    REFINANCIAMENTO = 2
    REFIN_PORTABILIDADE = 3
    PORTABILIDADE = 4
    NOVO_AUMENTO_SALARIAL = 5
    SAQUE_COMPLEMENTAR = 6


class EnumTipoAnexo(object):
    CCB = 1
    DOCUMENTO_FRENTE = 2
    DOCUMENTO_VERSO = 3
    CNH = 8
    SELFIE = 4
    DOCUMENTOS_ADICIONAIS = 12
    FOTO_PROVA_VIDA = 5
    COMPROVANTE_ENDERECO = 6
    COMPROVANTE_FINANCEIRO = 7
    REPASSE = 11
    ARQUIVO_RETORNO_RESERVA = 22
    FRENTE_CNH = 13
    VERSO_CNH = 14
    TERMOS_E_ASSINATURAS = 15
    CONTRACHEQUE = 16
    DOCUMENTO_ASSINADO_FISICAMENTE = 17
    DOCUMENTO_FRENTE_ROGADO = 18
    DOCUMENTO_VERSO_ROGADO = 19
    CNH_ROGADO = 20
    DOCUMENTO_FRENTE_TESTEMUNHA = 9
    DOCUMENTO_VERSO_TESTEMUNHA = 10
    CNH_TESTEMUNHA = 21


TIPO_ANEXO_DESC = {
    EnumTipoAnexo.CNH: 'cnh',
    EnumTipoAnexo.COMPROVANTE_ENDERECO: 'comprovante_endereco',
    EnumTipoAnexo.CONTRACHEQUE: 'contracheque',
    EnumTipoAnexo.DOCUMENTOS_ADICIONAIS: 'adicional',
    EnumTipoAnexo.DOCUMENTO_FRENTE: 'rg_frente',
    EnumTipoAnexo.DOCUMENTO_VERSO: 'rg_verso',
    EnumTipoAnexo.SELFIE: 'selfie',
}


class EnumContratoStatus(object):
    DIGITACAO = 1
    AGUARDANDO_FORMALIZACAO = 2
    FORMALIZADO = 3
    MESA = 4
    EM_AVERBACAO = 5
    PAGO = 6
    CANCELADO = 0
    ERRO = 9


class NomeAverbadoras(IntEnum):
    FACIL = 1
    ZETRASOFT = 2
    QUANTUM = 3
    DATAPREV_BRB = 4
    DATAPREV_PINE = 5
    SERPRO = 6
    NEOCONSIG = 7


class EnumTipoComunicacao(object):
    ARQUIVO = 1
    API = 2


class EnumSeguradoras(object):
    TEM_SAUDE = 1
    GENERALI = 2
    SABEMI = 3


class EnumTipoPlano(object):
    PRATA = 1
    OURO = 2
    DIAMANTE = 3


class EnumTipoMargem(object):
    MARGEM_COMPRA = 1
    MARGEM_SAQUE = 2
    MARGEM_UNICA = 3
    MARGEM_UNIFICADA = 4


class ExportType(str, Enum):
    GENERAL = 'geral'
    FINALIZATION = 'finalizacao'
    BALANCE_RETURN = 'retorno_saldo'


class SiapeLinkTypeEnum(IntEnum):
    SERVIDOR = 1
    PENCIONISTA = 2


class EnumArquivosSeguros(IntEnum):
    VIDA_SIAPE = 1
    VIDA_INSS = 2
    OURO_INSS = 3
    DIAMANTE_INSS = 4
    OURO_DEMAIS_CONVENIOS = 5
    DIAMANTE_DEMAIS_CONVENIOS = 6
    SABEMI_VIDA_PRATA = 7
    SABEMI_VIDA_OURO_PRESTAMISTA = 8
    SABEMI_VIDA_DIAMANTE_PRESTAMISTA = 9

    @staticmethod
    def get_nome_arquivo(tipo):
        mapeamento_arquivos = {
            EnumArquivosSeguros.VIDA_SIAPE: 'TERMO VIDA SIAPE.pdf',
            EnumArquivosSeguros.VIDA_INSS: 'TERMO VIDA INSS.pdf',
            EnumArquivosSeguros.OURO_INSS: 'TERMO OURO INSS.pdf',
            EnumArquivosSeguros.DIAMANTE_INSS: 'TERMO DIAMANTE INSS.pdf',
            EnumArquivosSeguros.OURO_DEMAIS_CONVENIOS: 'TERMO OURO DEMAIS CONVENIOS.pdf',
            EnumArquivosSeguros.DIAMANTE_DEMAIS_CONVENIOS: 'TERMO DIAMANTE DEMAIS CONVENIOS.pdf',
            EnumArquivosSeguros.SABEMI_VIDA_PRATA: 'termo_adesao_vida_prata.pdf',
            EnumArquivosSeguros.SABEMI_VIDA_OURO_PRESTAMISTA: 'termo_adesao_vida_prestamista_ouro.pdf',
            EnumArquivosSeguros.SABEMI_VIDA_DIAMANTE_PRESTAMISTA: 'termo_adesao_vida_prestamista_diamante.pdf',
        }

        return mapeamento_arquivos.get(tipo)

        # Exemplo de uso
        # nome_arquivo = EnumArquivosSeguros.get_nome_arquivo(EnumArquivosSeguros.VIDA_SIAPE)


class EnumTipoPendencia(IntEnum):
    SENHA_DE_AVERBACAO = 1
    CONTRACHEQUE = 2
    DEMAIS_ANEXOS_DE_AVERBACAO = 3


class EnumStatusCancelamento(object):
    CANCELAMENTO_PEDIDO = 1
    CANCELAMENTO_INADIMPLENCIA = 2
    CANCELAMENTO_SINISTRO = 3
    CANCELAMENTO_TROCA = 4


class EnumEscolaridade:
    ENSINO_FUNDAMENTAL = 1
    ENSINO_MEDIO = 2
    ENSINO_SUPERIOR = 3
    POS_GRADUADO = 4
    ANALFABETO = 5

    @staticmethod
    def choices():
        return (
            (EnumEscolaridade.ENSINO_FUNDAMENTAL, 'Ensino Fundamental'),
            (EnumEscolaridade.ENSINO_MEDIO, 'Ensino Médio'),
            (EnumEscolaridade.ENSINO_SUPERIOR, 'Ensino Superior'),
            (EnumEscolaridade.POS_GRADUADO, 'Pós Graduado'),
            (EnumEscolaridade.ANALFABETO, 'Analfabeto'),
        )


class EnumGrauParentesco:
    PAI = 1
    MAE = 2
    FILHO = 3
    CONJUGE = 4
    IRMAO = 5

    @staticmethod
    def choices() -> tuple:
        return (
            (EnumGrauParentesco.PAI, 'Pai'),
            (EnumGrauParentesco.MAE, 'Mãe'),
            (EnumGrauParentesco.FILHO, 'Filho'),
            (EnumGrauParentesco.CONJUGE, 'Cônjuge'),
            (EnumGrauParentesco.IRMAO, 'Irmão'),
        )


STATUS_REPROVADOS = [
    ContractStatus.REPROVADA_FINALIZADA.value,
    ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
    ContractStatus.RECUSADA_AVERBACAO.value,
    ContractStatus.REPROVADA_POLITICA_INTERNA.value,
    ContractStatus.REPROVADA_MESA_CORBAN.value,
    ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
    ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
    ContractStatus.REPROVADO.value,
    ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
]

ENDORSED_REFIN_STATUSES = [
    ContractStatus.REPROVADA_FINALIZADA.AGUARDANDO_AVERBACAO_REFIN.value,
    ContractStatus.REPROVADA_FINALIZADA.AGUARDANDO_DESEMBOLSO_REFIN.value,
    ContractStatus.REPROVADA_FINALIZADA.INT_FINALIZADO_DO_REFIN.value,
]

QI_TECH_ENDPOINTS = {
    'credit_transfer': '/v2/credit_transfer/proposal/',
    'debt': '/debt?calculate_spread=False&eval_present_value=True&calculate_delay=True&key=',
}
