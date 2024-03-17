import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta

from core.models.parametro_produto import ParametrosProduto
from simulacao.constants import EnumParametroSistema
from simulacao.models.Data import Data
from simulacao.utils import data_atual_sem_hora

logger = logging.getLogger('digitacao')


def obter_dias_uteis(data_inicial, data_final):
    qtd_dias_uteis = None

    try:
        qtd_dias_uteis = Data.objects.filter(
            dt_data__range=(data_inicial, data_final), fl_dia_util=True
        ).count()

    except Exception as e:
        logger.error(f'Erro ao obter dias uteis (obter_dias_uteis): {e}')
        raise

    return qtd_dias_uteis


def definir_data_primeiro_vencimento(tipo_produto):
    data_primeiro_vencimento = None

    try:
        data_atual = datetime.strptime(data_atual_sem_hora(), '%Y-%m-%d')
        data_atual_primeiro_dia_mes = datetime(data_atual.year, data_atual.month, 1)

        qtd_dias_uteis_base_simulacao = get_parametro_sistema(
            EnumParametroSistema.QUANTIDADE_DIAS_UTEIS_BASE_SIMULACAO, tipo_produto
        )
        qtd_meses_add_qdo_dias_menor_igual_base = get_parametro_sistema(
            EnumParametroSistema.MESES_PARA_ADICIONAR_QUANDO_DIAS_UTEIS_MENOR_IGUAL_BASE,
            tipo_produto,
        )
        qtd_meses_add_qdo_dias_maior_base = get_parametro_sistema(
            EnumParametroSistema.MESES_PARA_ADICIONAR_QUANDO_DIAS_UTEIS_MAIOR_BASE,
            tipo_produto,
        )
        dia_vencimento_padrao_simulacao = get_parametro_sistema(
            EnumParametroSistema.DIA_VENCIMENTO_PADRAO_SIMULACAO, tipo_produto
        )

        qtd_dias_uteis = obter_dias_uteis(data_atual_primeiro_dia_mes, data_atual)

        if qtd_dias_uteis <= qtd_dias_uteis_base_simulacao:
            data_base = data_atual + relativedelta(
                months=qtd_meses_add_qdo_dias_menor_igual_base
            )
        else:
            data_base = data_atual + relativedelta(
                months=qtd_meses_add_qdo_dias_maior_base
            )

        data_primeiro_vencimento = datetime(
            data_base.year, data_base.month, dia_vencimento_padrao_simulacao
        )

    except Exception as e:
        logger.error(
            f'Erro ao definir data primeiro vencimento (definir_data_primeiro_vencimento): {e}'
        )
        raise

    return data_primeiro_vencimento


def get_parametro_sistema(parametro, tipo_produto):
    parametros_produto = ParametrosProduto.objects.filter(
        tipoProduto=tipo_produto
    ).first()

    match parametro:
        case EnumParametroSistema.DIAS_LIMITE_PARA_DESEMBOLSO:
            return parametros_produto.dias_limite_para_desembolso
        case EnumParametroSistema.VALOR_MINIMO_PARCELA:
            return parametros_produto.valor_minimo_parcela_simulacao
        case EnumParametroSistema.QUANTIDADE_DIAS_UTEIS_BASE_SIMULACAO:
            return parametros_produto.quantidade_dias_uteis_base_simulacao
        case EnumParametroSistema.MESES_PARA_ADICIONAR_QUANDO_DIAS_UTEIS_MENOR_IGUAL_BASE:
            return parametros_produto.meses_para_adicionar_quando_dias_uteis_menor_igual_base
        case EnumParametroSistema.MESES_PARA_ADICIONAR_QUANDO_DIAS_UTEIS_MAIOR_BASE:
            return parametros_produto.meses_para_adicionar_quando_dias_uteis_maior_base
        case EnumParametroSistema.DIA_VENCIMENTO_PADRAO_SIMULACAO:
            return parametros_produto.dia_vencimento_padrao_simulacao
        case EnumParametroSistema.VALOR_LIBERADO_CLIENTE_OPERACAO_MIN:
            return parametros_produto.valor_liberado_cliente_operacao_min
        case EnumParametroSistema.VALOR_LIBERADO_CLIENTE_OPERACAO_MAX:
            return parametros_produto.valor_liberado_cliente_operacao_max
        case _:
            return None
