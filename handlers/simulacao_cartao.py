import calendar
import logging
from datetime import datetime, timedelta

import numpy as np

logger = logging.getLogger('digitacao')


def calcula_simulacao_iof(
    valor_saque, produto_convenio, parametros_backoffice, possui_saque=None
):
    """Realiza o cálculo das taxas CET ao mês e ao ano com base na
    escolha do cliente de saque ou não
    """
    valor_saque = float(valor_saque)

    taxas = {'valor_saque': valor_saque}
    # CALCULO DIAS CORRIDOS DE FATURA(SAQUE E VENCIMENTO):
    corte = produto_convenio.corte
    vencimento_fatura = produto_convenio.data_vencimento_fatura
    criacao_do_contrato = datetime.now().date()
    data_vencimento = criacao_do_contrato.replace(day=1)
    if criacao_do_contrato.day > vencimento_fatura:
        data_vencimento = criacao_do_contrato.replace(day=1) + timedelta(days=31)

    dia_simulacao = datetime.now().day

    try:
        if vencimento_fatura < corte:
            if (dia_simulacao > corte and dia_simulacao > vencimento_fatura) or (
                dia_simulacao < corte and dia_simulacao <= vencimento_fatura
            ):
                data_vencimento = data_vencimento.replace(day=1) + timedelta(days=31)
        elif dia_simulacao >= corte and dia_simulacao <= vencimento_fatura:
            data_vencimento = data_vencimento.replace(day=1) + timedelta(days=31)

        ultimo_dia_mes = calendar.monthrange(
            data_vencimento.year, data_vencimento.month
        )[1]
        if vencimento_fatura <= ultimo_dia_mes:
            data_vencimento = data_vencimento.replace(day=vencimento_fatura)
        else:
            proximo_mes = data_vencimento.replace(day=1) + timedelta(days=31)
            dias_excedentes = vencimento_fatura - ultimo_dia_mes
            data_vencimento = proximo_mes.replace(day=dias_excedentes)

    except Exception as e:
        logger.error(
            f'Erro ao simular saque. Verificar parametrização (calcula_simulacao_iof): {e}'
        )
        return {'Erro': 'Erro ao simular saque. Verificar parametrização'}

    quantidade_dias = (data_vencimento - criacao_do_contrato).days

    vencimento_fatura = data_vencimento.isoformat()

    # PARAMETROS VINDOS DE: PARAMETROS - BACKOFFICE
    taxa_iof_diario = float(parametros_backoffice.taxa_iof_diario)  # 0,0082%
    taxa_iof_adicional = float(parametros_backoffice.taxa_iof_adicional)  # 0,38
    valor_iof_diario = float(parametros_backoffice.valor_iof_diario)  # 0,000082
    valor_iof_adicional = float(parametros_backoffice.valor_iof_adicional)  # 0,000038
    # valor_seguro_iof = float(parametros_backoffice.valor_iof_seguro)  # 0
    # valor_outras_taxas = float(parametros_backoffice.valor_outros)  # 0

    # PARAMETROS VINDOS DE: PARAMETROS - CONVENIO
    taxa_produto = float(produto_convenio.taxa_produto)  # 4.5%
    valor_taxa_produto = float(produto_convenio.valor_taxa_produto)  # 0.045

    # TAXA ANUAL DO PRODUTO
    taxa_anual_produto = (
        np.round(((1 + valor_taxa_produto) ** (365 / 30)) - 1, 4) * 100
    )  # Em %
    taxa_anual_produto = np.round(taxa_anual_produto, 4)
    # CALCULO CET MENSAL E ANUAL
    # TALVEZ É USADA NO INSS
    # cet_mensal = np.round((taxa_produto + (taxa_iof_diario * 30) + taxa_iof_adicional + valor_outras_taxas), 4)  # Em %

    # SOMENTE PARA SAQUE
    cet_mensal = np.round(
        (taxa_produto + (taxa_iof_diario * quantidade_dias) + taxa_iof_adicional), 2
    )  # Em %
    cet_anual = np.round(((((1 + (cet_mensal / 100)) ** (365 / 30)) - 1) * 100), 2)

    # CALCULO DO VALOR DO IOF DE ACORDO COM O SAQUE
    if possui_saque:
        taxa_iof_dias = (quantidade_dias * taxa_iof_diario) / 100

        valor_iof_diario_em_dinheiro = np.round(valor_saque * taxa_iof_dias, 2)
        valor_iof_adicional_em_dinheiro = np.round(valor_saque * valor_iof_adicional, 2)
        saque_cet = (valor_saque * cet_mensal) / 100
        total_financiado = np.round(valor_saque + saque_cet, 2)

        valor_iof_total = np.round(
            valor_iof_diario_em_dinheiro + valor_iof_adicional_em_dinheiro, 2
        )

        taxas['valor_iof_diario_em_dinheiro'] = valor_iof_diario_em_dinheiro
        taxas['valor_iof_adicional_em_dinheiro'] = valor_iof_adicional_em_dinheiro
        taxas['valor_iof_diario'] = format(valor_iof_diario, '.6f')
        taxas['valor_iof_adicional'] = format(valor_iof_adicional, '.5f')
        taxas['valor_total_financiado'] = total_financiado
        taxas['valor_iof_total'] = valor_iof_total

    taxas['taxa_produto'] = taxa_produto
    taxas['taxa_anual_produto'] = taxa_anual_produto
    taxas['taxa_iof_diario'] = taxa_iof_diario
    taxas['taxa_iof_adicional'] = taxa_iof_adicional
    taxas['cet_anual'] = cet_anual
    taxas['cet_mensal'] = cet_mensal
    taxas['vencimento'] = vencimento_fatura

    return taxas


def calcula_simulacao_iof_saque_complementar(
    valor_saque, produto_convenio, parametros_backoffice
):
    """Realiza o cálculo das taxas CET ao mês e ao ano com base na
    escolha do cliente de saque ou não
    """
    valor_saque = float(valor_saque)

    # CALCULO DIAS CORRIDOS DE FATURA(SAQUE E VENCIMENTO):
    corte = produto_convenio.corte
    vencimento_fatura = produto_convenio.data_vencimento_fatura
    criacao_do_contrato = datetime.now().date()
    data_vencimento = criacao_do_contrato.replace(day=1)
    if criacao_do_contrato.day > vencimento_fatura:
        data_vencimento = criacao_do_contrato.replace(day=1) + timedelta(days=31)

    dia_simulacao = datetime.now().day

    try:
        if vencimento_fatura < corte:
            if (dia_simulacao > corte and dia_simulacao > vencimento_fatura) or (
                dia_simulacao < corte and dia_simulacao <= vencimento_fatura
            ):
                data_vencimento = data_vencimento.replace(day=1) + timedelta(days=31)
        elif dia_simulacao >= corte and dia_simulacao <= vencimento_fatura:
            data_vencimento = data_vencimento.replace(day=1) + timedelta(days=31)

        ultimo_dia_mes = calendar.monthrange(
            data_vencimento.year, data_vencimento.month
        )[1]
        if vencimento_fatura <= ultimo_dia_mes:
            data_vencimento = data_vencimento.replace(day=vencimento_fatura)
        else:
            proximo_mes = data_vencimento.replace(day=1) + timedelta(days=31)
            dias_excedentes = vencimento_fatura - ultimo_dia_mes
            data_vencimento = proximo_mes.replace(day=dias_excedentes)

    except Exception as e:
        logger.error(
            f'Erro ao simular saque. Verificar parametrização (calcula_simulacao_iof): {e}'
        )
        return {'Erro': 'Erro ao simular saque. Verificar parametrização'}

    quantidade_dias = (data_vencimento - criacao_do_contrato).days

    vencimento_fatura = data_vencimento.isoformat()

    # PARAMETROS VINDOS DE: PARAMETROS - BACKOFFICE
    taxa_iof_diario = float(parametros_backoffice.taxa_iof_diario)  # 0,0082%
    taxa_iof_adicional = float(parametros_backoffice.taxa_iof_adicional)  # 0,38
    valor_iof_diario = float(parametros_backoffice.valor_iof_diario)  # 0,000082
    valor_iof_adicional = float(parametros_backoffice.valor_iof_adicional)  # 0,000038
    # valor_seguro_iof = float(parametros_backoffice.valor_iof_seguro)  # 0
    # valor_outras_taxas = float(parametros_backoffice.valor_outros)  # 0

    # PARAMETROS VINDOS DE: PARAMETROS - CONVENIO
    taxa_produto = float(produto_convenio.taxa_produto)  # 4.5%
    valor_taxa_produto = float(produto_convenio.valor_taxa_produto)  # 0.045

    # TAXA ANUAL DO PRODUTO
    taxa_anual_produto = (
        np.round(((1 + valor_taxa_produto) ** (360 / 30)) - 1, 4) * 100
    )  # Em %

    # CALCULO CET MENSAL E ANUAL
    # TALVEZ É USADA NO INSS
    # cet_mensal = np.round((taxa_produto + (taxa_iof_diario * 30) + taxa_iof_adicional + valor_outras_taxas), 4)  # Em %

    # SOMENTE PARA SAQUE
    cet_mensal = np.round(
        (taxa_produto + (taxa_iof_diario * quantidade_dias) + taxa_iof_adicional), 2
    )  # Em %
    cet_anual = np.round(((((1 + (cet_mensal / 100)) ** (365 / 30)) - 1) * 100), 2)

    taxa_iof_dias = (quantidade_dias * taxa_iof_diario) / 100

    valor_iof_diario_em_dinheiro = np.round(valor_saque * taxa_iof_dias, 4)
    valor_iof_adicional_em_dinheiro = np.round(valor_saque * valor_iof_adicional, 3)
    saque_cet = (valor_saque * cet_mensal) / 100
    total_financiado = np.round(valor_saque + saque_cet, 2)

    valor_iof_total = np.round(
        valor_iof_diario_em_dinheiro + valor_iof_adicional_em_dinheiro, 2
    )

    return {
        'valor_saque': valor_saque,
        'valor_iof_diario_em_dinheiro': valor_iof_diario_em_dinheiro,
        'valor_iof_adicional_em_dinheiro': valor_iof_adicional_em_dinheiro,
        'valor_iof_diario': format(valor_iof_diario, '.6f'),
        'valor_iof_adicional': format(valor_iof_adicional, '.5f'),
        'valor_total_financiado': total_financiado,
        'valor_iof_total': valor_iof_total,
        'taxa_produto': taxa_produto,
        'taxa_anual_produto': taxa_anual_produto,
        'taxa_iof_diario': taxa_iof_diario,
        'taxa_iof_adicional': taxa_iof_adicional,
        'cet_anual': cet_anual,
        'cet_mensal': cet_mensal,
        'vencimento': vencimento_fatura,
    }
