from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from simulacao.models import FaixaIdade


def calcular_diferenca_datas(data_inicial, data_final):
    diferenca = relativedelta(data_final, data_inicial)

    return diferenca.years, diferenca.months, diferenca.days


def anos_de_beneficio(data_criacao):
    hoje = date.today()
    anos, _, _ = calcular_diferenca_datas(data_criacao, hoje)
    return anos


def meses_de_beneficio(data_criacao):
    hoje = date.today()
    anos, meses, _ = calcular_diferenca_datas(data_criacao, hoje)
    meses = (anos * 12) + meses
    return meses


def idade_na_concessao(data_nascimento, data_concessao):
    anos, _, _ = calcular_diferenca_datas(data_nascimento, data_concessao)
    return anos


def calcular_idade_anos_meses_dias(data_nascimento):
    if isinstance(data_nascimento, str):
        data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
    hoje = datetime.now().date()

    # Cálculo de diferença em anos, meses e dias
    anos = (
        hoje.year
        - data_nascimento.year
        - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
    )

    if hoje.month >= data_nascimento.month:
        meses = hoje.month - data_nascimento.month
    else:
        meses = 12 - data_nascimento.month + hoje.month

    if hoje.day >= data_nascimento.day:
        dias = hoje.day - data_nascimento.day
    else:
        dias = (
            (hoje - datetime(hoje.year, hoje.month, 1).date()).days
            + (
                data_nascimento
                - datetime(data_nascimento.year, data_nascimento.month, 1).date()
            ).days
            + 1
        )

    return anos, meses, dias


def validar_faixa_idade(contrato):
    from django.db.models import Q

    from contract.models.contratos import Contrato, Portabilidade
    from contract.products.cartao_beneficio.constants import ContractStatus

    contrato_portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
    valor_cliente = 0
    contratos_cliente = (
        Contrato.objects.filter(cliente=contrato.cliente)
        .exclude(
            Q(contrato_portabilidade__status=ContractStatus.REPROVADO.value)
            | Q(
                contrato_portabilidade__status=ContractStatus.REPROVADA_POLITICA_INTERNA.value
            )
            | Q(
                contrato_portabilidade__status=ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value
            )
            | Q(
                contrato_portabilidade__status=ContractStatus.REPROVADA_MESA_FORMALIZACAO.value
            )
        )
        .filter(contrato_portabilidade__status=ContractStatus.SALDO_RETORNADO.value)
    )
    for contrato_cliente in contratos_cliente:
        saldo = (
            Portabilidade.objects.filter(contrato=contrato_cliente)
            .first()
            .saldo_devedor_atualizado
        )
        valor_cliente += saldo
    faixas = FaixaIdade.objects.all()
    idade_anos, idade_meses, _ = calcular_idade_anos_meses_dias(
        contrato_cliente.cliente.dt_nascimento
    )
    idade_cliente = float(f'{idade_anos}.{idade_meses:02}')

    prazo_cliente = contrato_portabilidade.numero_parcela_atualizada
    resposta = {}
    for faixa in faixas:
        if faixa.nu_idade_minima <= idade_cliente <= faixa.nu_idade_maxima:
            if faixa.nu_prazo_minimo <= prazo_cliente <= faixa.nu_prazo_maximo:
                if faixa.vr_minimo <= valor_cliente <= faixa.vr_maximo:
                    resposta['regra_aprovada'] = True
                else:
                    resposta['regra_aprovada'] = False
                    resposta['motivo'] = 'Fora da Politica'
            else:
                resposta['regra_aprovada'] = False
                resposta['motivo'] = 'Fora da Politica'
            return resposta
        else:
            resposta['regra_aprovada'] = True
    return resposta
