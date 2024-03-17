import json
import logging
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib import messages

from api_log.models import LogCliente, RetornosDock, StatusCobrancaDock
from contract.constants import EnumTipoPlano
from handlers.dock_formalizacao import gerar_token

url_token = settings.DOCK_URL_TOKEN
url_base = settings.DOCK_URL_BASE
client_id = settings.DOCK_CLIENT_ID
client_password = settings.DOCK_CLIENT_PASSWORD


logger = logging.getLogger('digitacao')


def solicitar_cobranca(
    contrato, plano, cartao_beneficio, cliente_cartao, request=None, premio_bruto=None
):
    if plano.tipo_plano == EnumTipoPlano.PRATA:
        if request is not None:
            messages.error(
                request,
                'Não existem lançamento para o plano Prata',
            )
    elif plano.tipo_plano == EnumTipoPlano.OURO:
        id_tipo_ajuste = 187
        msg_atendimento = 'Contratacao seguro Ouro'
    elif plano.tipo_plano == EnumTipoPlano.DIAMANTE:
        id_tipo_ajuste = 189
        msg_atendimento = 'Contratacao seguro Diamante'
    cliente_cartao = contrato.cliente_cartao_contrato.get()

    try:
        valor_plano = Decimal(premio_bruto)
    except Exception as e:
        print(e)
        valor_plano = Decimal(premio_bruto.replace('.', '').replace(',', '.'))

    payload = json.dumps({
        'idTipoAjuste': id_tipo_ajuste,
        'dataAjuste': str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
        'valorAjuste': f'{valor_plano}',
        'identificadorExterno': '',
        'idEstabelecimento': '',
        'flagAtendimento': True,
        'mensagemAtendimento': msg_atendimento,
        'descricaoEstabelecimentoExterno': '',
        'idConta': cliente_cartao.id_conta_dock,
        'rbtranFields': {},
    })

    auth = gerar_token(client_id, client_password)
    url = f'{url_base}/ajustes-financeiros'

    headers = {'Content-Type': 'application/json', 'Authorization': f'{auth}'}
    response = requests.request('POST', url, headers=headers, data=payload)
    log_api = LogCliente.objects.get(cliente=contrato.cliente)

    RetornosDock.objects.create(
        log_api=log_api,
        id_cliente=cliente_cartao.id_conta_dock,
        payload=response.json(),
        payload_envio=payload,
        nome_chamada='Cobrança do Plano na Fatura do Cliente',
        codigo_retorno=response.status_code,
        cliente=contrato.cliente,
    )

    if response.status_code in {200, 202}:
        print('resposta DOCK')
        StatusCobrancaDock.objects.create(
            cliente=contrato.cliente, status_cobranca='Lançado com sucesso'
        )
        if request is not None:
            messages.success(
                request,
                f'Plano {plano}, lançado com sucesso.',
            )
    else:
        logger.error(
            f'Plano {plano}, Erro no Lançamento: {response.text} Response content {response.content}'
        )
        StatusCobrancaDock.objects.create(
            cliente=contrato.cliente, status_cobranca='Erro no Lançamento'
        )
        if request is not None:
            messages.error(
                request,
                f'Plano {plano}, Erro no Lançamento',
            )


def solicitar_cobranca_operacoes(
    contrato, plano, cartao_beneficio, cliente_cartao, request=None
):
    if plano.tipo_plano == EnumTipoPlano.PRATA:
        if request is not None:
            messages.error(
                request,
                'Não existem lançamento para o plano Prata',
            )
    elif plano.tipo_plano == EnumTipoPlano.OURO:
        id_tipo_ajuste = 184
        msg_atendimento = 'Estorno seguro Ouro'
    elif plano.tipo_plano == EnumTipoPlano.DIAMANTE:
        id_tipo_ajuste = 185
        msg_atendimento = 'Estorno seguro Diamante'

    cliente_cartao = contrato.cliente_cartao_contrato.get()
    try:
        valor_plano = Decimal(plano.valor_segurado)
    except Exception as e:
        print(e)
        valor_plano = Decimal(plano.valor_segurado.replace('.', '').replace(',', '.'))

    payload = json.dumps({
        'idTipoAjuste': id_tipo_ajuste,
        'dataAjuste': str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
        'valorAjuste': f'{valor_plano}',
        'identificadorExterno': '',
        'idEstabelecimento': '',
        'flagAtendimento': True,
        'mensagemAtendimento': msg_atendimento,
        'descricaoEstabelecimentoExterno': '',
        'idConta': cliente_cartao.id_conta_dock,
        'rbtranFields': {},
    })

    auth = gerar_token(client_id, client_password)
    url = f'{url_base}/ajustes-financeiros'

    headers = {'Content-Type': 'application/json', 'Authorization': f'{auth}'}
    response = requests.request('POST', url, headers=headers, data=payload)
    log_api = LogCliente.objects.get(cliente=contrato.cliente)

    RetornosDock.objects.create(
        log_api=log_api,
        id_cliente=cliente_cartao.id_conta_dock,
        payload=response.json(),
        payload_envio=payload,
        nome_chamada='Estorno do Plano na Fatura do Cliente',
        codigo_retorno=response.status_code,
        cliente=contrato.cliente,
    )

    if response.status_code in {200, 202}:
        print('resposta DOCK')
        StatusCobrancaDock.objects.create(
            cliente=contrato.cliente, status_cobranca='Lançado com sucesso'
        )
        if request is not None:
            messages.success(
                request,
                f'Plano {plano}, lançado com sucesso.',
            )
    else:
        logger.error(
            f'Plano {plano}, Erro no Lançamento: {response.text} Response content {response.content}'
        )
        StatusCobrancaDock.objects.create(
            cliente=contrato.cliente, status_cobranca='Erro no Lançamento'
        )
        if request is not None:
            messages.error(
                request,
                f'Plano {plano}, Erro no Lançamento',
            )
