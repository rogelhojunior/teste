import logging
from datetime import datetime

from rest_framework.exceptions import ValidationError

from contract.constants import EnumTipoProduto
from contract.models.contratos import (
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
)
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.utils import (
    calcular_idade_anos_meses_dias,
    idade_na_concessao,
    meses_de_beneficio,
)
from core.models import Cliente
from simulacao.models import FaixaIdade


def get_limites_idade_e_duracoes(
    data_concessao_beneficio: datetime.date,
    data_limite: datetime,
) -> tuple[list, list]:
    """
    Retorna os limites de idade e durações baseado na data de concessão do benefício e data limite.
    :param data_concessao_beneficio: Data em que o benefício foi concedido
    :param data_limite: Data limite para verificação do benefício.
    :returns: Uma tupla de duas listas, uma de limites_idade de outra de durações do benefício.
    """
    if data_concessao_beneficio < data_limite:
        limites_idade = []
        duracoes = []
    elif data_concessao_beneficio.year < 2021:
        limites_idade = [21, 27, 30, 41, 44]
        duracoes = [3, 6, 10, 15, 20]
    else:
        limites_idade = [22, 28, 31, 42, 45]
        duracoes = [3, 6, 10, 15, 20]

    return limites_idade, duracoes


def valida_duracao_beneficio_dentro_faixa_limite(
    data_concessao_beneficio,
    data_limite,
    idade_concessao,
    meses_beneficio,
    parcelas,
) -> bool:
    """
    Valida se, baseado na data_limite, idade_concessao, meses_beneficio e parcelas.
    :param data_concessao_beneficio: Data de concessão do benefício
    :param data_limite: Data limite para verificação do benefício
    :param idade_concessao: Idade na concessão do benefício
    :param meses_beneficio: Meses restantes do benefício
    :param parcelas: Parcelas daquele contrato
    :return: True ou False, dependendo se passou nas regras de idade.
    """
    limites_idade, duracoes = get_limites_idade_e_duracoes(
        data_concessao_beneficio,
        data_limite,
    )
    for i, limite in enumerate(limites_idade):
        if idade_concessao < limite:
            duracao_beneficio = duracoes[i] * 12 - meses_beneficio
            return not (duracao_beneficio < parcelas)
    return True


def get_idade_cliente_anos_meses(cliente: Cliente) -> float:
    """
    Calcula a data do cliente
    :param cliente: Cliente instance
    :return: Idade do cliente em ANOS.MESES
    """
    idade_anos, idade_meses, _ = calcular_idade_anos_meses_dias(cliente.dt_nascimento)
    return float(f'{idade_anos}.{idade_meses:02}')


def valida_faixa_idade(
    cliente: Cliente,
    parcelas: int,
    valor_cliente: float,
) -> bool:
    """
    Tenta obter a faixa de idade em que o cliente se encaixa.
    Verifica a idade, prazo e valor que pode contratar.
    :param cliente: Cliente para ser verificado
    :param parcelas: Quantidade de parcelas
    :param valor_cliente: Valor que o cliente possui.
    :return: Boolean com a avaliação de faixa de idade
    """
    idade_cliente = get_idade_cliente_anos_meses(cliente)
    try:
        FaixaIdade.objects.get(
            nu_idade_minima__lte=idade_cliente,
            nu_idade_maxima__gte=idade_cliente,
            nu_prazo_minimo__lte=parcelas,
            nu_prazo_maximo__gte=parcelas,
            vr_minimo__lte=valor_cliente,
            vr_maximo__gte=valor_cliente,
        )
        return True
    except FaixaIdade.DoesNotExist:
        return False


class BaseValidadorRegrasBeneficio:
    _NUMEROS_ESPECIE = {2, 21, 93}
    _DATA_LIMITE = '2015-06-17'
    _TIPO_PRODUTO = None  # Pode ser uma lista ou apenas uma variável

    def __init__(self):
        self.data_nascimento = None
        self.idade_concessao = None
        self.data_concessao_beneficio = None

        self.meses_beneficio = None
        self.numero_especie = None
        self.data_limite = self.get_data_limite()
        self.parcelas = None

    def get_data_limite(self) -> datetime.date:
        """
        Obtém a data limite como um objeto datetime
        """
        return datetime.strptime(self._DATA_LIMITE, '%Y-%m-%d').date()

    def valida_numero_especie(self, numero_especie: int) -> bool:
        """
        Valida o número da espécie, baseado na variável _NUMEROS_ESPECIE.
        """
        return numero_especie in self._NUMEROS_ESPECIE

    def validar_regra_morte(self) -> dict:
        """
        Valida as regras para permitir que o fluxo siga normalmente.
        Inicialmente valida se o tipo de produto é compatível e se tem a variável de parcelas definida.
        :return: True ou False, dependendo se a regra foi ou não aprovada.
        """
        if not self.data_concessao_beneficio:
            return {
                'regra_aprovada': False,
                'motivo': 'Não possui data de concessão',
            }

        self.idade_concessao = idade_na_concessao(
            self.data_nascimento,
            self.data_concessao_beneficio,
        )
        self.meses_beneficio = meses_de_beneficio(self.data_concessao_beneficio)

        resposta = {
            'regra_aprovada': True,
        }
        if self.valida_numero_especie(self.numero_especie):
            if valida_duracao_beneficio_dentro_faixa_limite(
                self.data_concessao_beneficio,
                self.data_limite,
                self.idade_concessao,
                self.meses_beneficio,
                self.parcelas,
            ):
                resposta['regra_aprovada'] = True
                resposta['motivo'] = '-'
            else:
                resposta['regra_aprovada'] = False
                resposta['motivo'] = 'Fora da Politica'
        return resposta


class ValidadorRegrasBeneficioContrato(BaseValidadorRegrasBeneficio):
    """
    Classe base para as validações relacionadas ao contrato do cliente.
    Pensada para validar o modelo de contrato
    Para conseguir definir os numeros_especie, consultar a documentação:
    - https://docs.qitech.com.br/documentation/manual_inss/manual_credito_novo/index.html

    """

    def __init__(self, contrato: Contrato, dados_in100: DadosIn100):
        """
        Salva o contrato, cliente e dados_in100.
        Cria as variáveis de concessão, nascimento e parcelas.
        A variável de parcelas precisa ser criada nas classes que herdarem

        """
        super().__init__()
        self.contrato = contrato

        self.validar_dados_entrada()

        self.dados_in100 = dados_in100
        self.data_concessao_beneficio = self.parse_obj_to_date(
            self.dados_in100.dt_expedicao_beneficio
        )
        self.data_nascimento = self.contrato.cliente.dt_nascimento

        self.numero_especie = self.dados_in100.cd_beneficio_tipo
        self.idade_concessao = None
        self.meses_beneficio = None
        self.parcelas = None
        self.instance = None

    def parse_obj_to_date(self, obj):
        if obj and isinstance(obj, str):
            return datetime.fromisoformat(obj).date()
        return obj

    def validar_dados_entrada(self):
        self.validar_tipo_produto()
        self.validar_cliente()

    def validar_cliente(self):
        """
        Valida se o contrato possui cliente. Necessário, pois a busca dos DadosIn100 precisa de cliente.
        """
        if not self.contrato.cliente:
            raise ValidationError({
                'erro': 'Este contrato não possui cliente! Apenas validações de contrato com cliente podem ser feitas.'
            })

    def valida_parcelas(self):
        """
        Valida apenas se a variável parcelas não está vazia.
        """
        if not self.parcelas:
            raise ValidationError({
                'erro': 'Você precisa definir a variável parcelas na classe herdada.'
            })

    def validar_tipo_produto(self):
        """
        Valida o tipo do produto, se faz parte dos planejados ou não.

        Caso não tenha sido definido o tipo produto
        Caso o tipo_produto não faça parte dos _TIPO_PRODUTO definidos
        """
        if not self._TIPO_PRODUTO:
            raise ValidationError({
                'erro': 'Você precisa definir a variável tipo_produto na classe herdada.'
            })
        if (
            isinstance(self._TIPO_PRODUTO, list)
            and self.contrato.tipo_produto not in self._TIPO_PRODUTO
        ) or (
            isinstance(self._TIPO_PRODUTO, int)
            and self.contrato.tipo_produto != self._TIPO_PRODUTO
        ):
            raise ValidationError({
                'erro': f'Este produto {self.contrato.tipo_produto} não pode ser utilizado nessa classe.'
            })

    def get_limites_idade_e_duracoes(
        self, data_limite: datetime
    ) -> tuple[list[int], list[int]]:
        """
        Retorna os limites de idade e durações baseado na data de concessão do benefício e data limite.
        """
        if self.data_concessao_beneficio < data_limite:
            limites_idade = []
            duracoes = []
        elif self.data_concessao_beneficio.year < 2021:
            limites_idade = [21, 27, 30, 41, 44]
            duracoes = [3, 6, 10, 15, 20]
        else:
            limites_idade = [22, 28, 31, 42, 45]
            duracoes = [3, 6, 10, 15, 20]

        return limites_idade, duracoes

    def get_resposta(
        self,
        numero_especie: int,
        data_limite: datetime,
        idade_concessao: int,
        meses_beneficio: int,
    ) -> dict:
        """
        Retorna a resposta baseada nos parâmetros enviados.
        Necessário, pois uma classe pode implementar apenas o comportamento do get_resposta.
        """
        resposta = {
            'regra_aprovada': True,
        }
        if self.valida_numero_especie(numero_especie):
            if valida_duracao_beneficio_dentro_faixa_limite(
                self.data_concessao_beneficio,
                numero_especie,
                data_limite,
                idade_concessao,
                meses_beneficio,
            ):
                resposta['regra_aprovada'] = True
                resposta['motivo'] = '-'
            else:
                resposta['regra_aprovada'] = False
                resposta['motivo'] = 'Fora da Politica'
        return resposta

    def get_valor_contrato(self) -> float:
        raise NotImplementedError

    def validar(self) -> dict:
        """
        Executa todas as validações necessárias da classe.
        Valida se as parcelas foram definidas, pois é um parâmetro importante.
        Verifica se a resposta de validação de morte deu errado, então retorna a payload.
        Caso dê certo, retorna a payload de validar_regra_faixa_idade.
        """

        self.valida_parcelas()
        resposta_validar_regra_morte = self.validar_regra_morte()
        if not resposta_validar_regra_morte['regra_aprovada']:
            return resposta_validar_regra_morte

        return self.validar_regra_faixa_idade()

    def validar_regra_faixa_idade(self) -> dict:
        """
        Valida a faixa de idade do cliente.

        """
        valor_cliente = self.get_valor_contrato()

        idade_anos, idade_meses, _ = calcular_idade_anos_meses_dias(
            self.contrato.cliente.dt_nascimento
        )
        idade_cliente = float(f'{idade_anos}.{idade_meses:02}')

        resposta = {}
        # O cliente só pode estar em uma faixa de idade.
        # Pega a FaixaIdade em que a idade do cliente está entre a idade mínima e a máxima.
        try:
            faixa_idade = FaixaIdade.objects.get(
                nu_idade_minima__lte=idade_cliente,
                nu_idade_maxima__gte=idade_cliente,
            )
        except FaixaIdade.DoesNotExist:
            logging.error(
                f'O cliente {self.contrato.cliente} não encaixa em nem uma das faixas de idade.'
                f' Verificar dados do banco.'
            )
            return {
                'regra_aprovada': False,
                'motivo': 'Fora da Política. O cliente não se encaixa em nem uma das faixas de idade',
            }
        except FaixaIdade.MultipleObjectsReturned:
            logging.error(
                f'O cliente {self.contrato.cliente} se encaixou em múltiplas faixas de idade.'
                f' Verificar dados do banco.'
            )
            return {
                'regra_aprovada': False,
                'motivo': 'Fora da política. O cliente se encaixa em múltiplas faixas de idade.',
            }

        if faixa_idade.nu_prazo_minimo <= self.parcelas <= faixa_idade.nu_prazo_maximo:
            if faixa_idade.vr_minimo <= valor_cliente <= faixa_idade.vr_maximo:
                resposta['regra_aprovada'] = True
            else:
                resposta['regra_aprovada'] = False
                resposta['motivo'] = 'Fora da Politica'
        else:
            resposta['regra_aprovada'] = False
            resposta['motivo'] = 'Fora da Politica'

        return resposta


class ValidadorRegrasBeneficioContratoPortabilidade(ValidadorRegrasBeneficioContrato):
    """
    Classe que implementa as regras para o contrato de portabilidade.
    Caso seja necessária alguma validação específica,
     sobrescreva o método validar() e os outros necessários.
     Ex: Caso a regra de Margem Livre mude e as regras de limites e durações sejam diferentes,
            implemente apenas o método get_limites_idade_e_duracoes.
    """

    _TIPO_PRODUTO = EnumTipoProduto.PORTABILIDADE

    def __init__(self, contrato: Contrato, dados_in100: DadosIn100):
        """
        Inicializa os dados necessários para a validação da portabilidade.
        """
        super().__init__(contrato, dados_in100)
        self.instance = Portabilidade.objects.filter(contrato=self.contrato).first()
        self.parcelas = self.instance.numero_parcela_atualizada

    def get_valor_contrato(self) -> float:
        """
        Obtém a soma de todos os saldos do contrato PORTABILIDADE daquele cliente, com SALDO_RETORNADO.
        """
        valor_cliente = 0
        for contrato in Contrato.objects.filter(
            cliente=self.contrato.cliente,
            contrato_portabilidade__status=ContractStatus.SALDO_RETORNADO.value,
        ):
            saldo = (
                Portabilidade.objects.filter(contrato=contrato)
                .first()
                .saldo_devedor_atualizado
            )
            valor_cliente += saldo
        return valor_cliente


class ValidadorRegrasBeneficioContratoMargemLivre(ValidadorRegrasBeneficioContrato):
    """
    Classe que implementa as regras para o contrato de Margem Livre.
    Caso seja necessária alguma validação específica,
     sobrescreva o método validar() e os outros necessários.
     Ex: Caso a regra de Margem Livre mude e os números espécie sejam diferentes,
            implemente apenas o método validar_numero_especie.
    """

    _TIPO_PRODUTO = (
        EnumTipoProduto.MARGEM_LIVRE,
        EnumTipoProduto.INSS,
    )

    def __init__(self, contrato: Contrato, dados_in100: DadosIn100):
        """
        Inicializa os dados necessários para a validação da Margem Livre.
        """
        super().__init__(contrato, dados_in100)
        self.instance = MargemLivre.objects.filter(contrato=self.contrato).first()
        self.parcelas = self.instance.qtd_parcelas

    def get_valor_contrato(self) -> float:
        """
        Obtém o valor total daquele contrato de margem livre.
        """
        return self.instance.vr_contrato


class ValidadorRegrasBeneficioCliente(BaseValidadorRegrasBeneficio):
    """
    Valida as regras de benefício do cliente, baseadas no cpf e na dt_nascimento
    1. Obter cliente
    2. Validar se os dados In100 daquele cliente seguem as regras
    2.1. Validar regra de morte, pelo código recebido
    3 Retornar se aquele cliente possui dados in 100 e está dentro dos parâmetros.
    """

    def __init__(self, cliente: Cliente, dados_in100: DadosIn100):
        super().__init__()
        self.cliente = cliente
        self.data_nascimento = self.cliente.dt_nascimento
        self.dados_in100 = dados_in100
        self.numero_especie = self.dados_in100.cd_beneficio_tipo

        self.data_concessao_beneficio = self.dados_in100.dt_expedicao_beneficio
        self.idade_concessao = None
        self.meses_beneficio = None
        self.parcelas = None

    def set_parcelas(self, parcelas: int):
        """
        Atualiza a variável parcelas da classe
        :param parcelas:
        :return:
        """
        self.parcelas = parcelas


class ValidadorRegrasBeneficioContratoPortabilidadeRefinanciamento(
    ValidadorRegrasBeneficioContrato
):
    """
    Classe que implementa as regras para o contrato de Margem Livre.
    Caso seja necessária alguma validação específica,
     sobrescreva o método validar() e os outros necessários.
     Ex: Caso a regra de Margem Livre mude e os números espécie sejam diferentes,
            implemente apenas o método validar_numero_especie.
    """

    _TIPO_PRODUTO = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

    def __init__(
        self,
        contrato: Contrato,
        dados_in100: DadosIn100,
        refinancing: Refinanciamento,
    ):
        """
        Inicializa os dados necessários para a validação da Margem Livre.
        """
        super().__init__(contrato, dados_in100)
        self.instance = refinancing
        self.parcelas = self.instance.prazo

    def get_valor_contrato(self) -> float:
        """
        Obtém o valor total daquele contratos.
        """
        return (
            float(self.instance.valor_total_recalculado)
            if self.instance.valor_total_recalculado
            else float(self.instance.valor_total)
        )
