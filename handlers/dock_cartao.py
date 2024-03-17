import json
from datetime import datetime

import requests
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.conf import settings

from api_log.models import RetornosDock
from contract.constants import EnumContratoStatus, EnumTipoMargem
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core.utils import alterar_status
from custom_auth.models import UserProfile

URL = settings.DOCK_URL_BASE
logger = get_task_logger('cliente')


def cria_limte_cartao(
    auth,
    id_conta,
    id_cliente,
    contrato,
    cliente,
    log_api,
    contrato_cartao,
    user,
    produto_convenio,
    cliente_cartao,
):
    cria_limite_obj = {}
    try:
        if cliente_cartao.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
            consigned_limit = float(cliente_cartao.limite_pre_aprovado)
            purchase_limit = float(cliente_cartao.limite_pre_aprovado_compra)
            global_withdraw_limit = float(cliente_cartao.limite_pre_aprovado_saque)

            url = (
                f'{URL}/accounts/{id_conta}/limits?consigned_limit={consigned_limit}'
                f'&purchase_limit={purchase_limit}&global_withdraw_limit={global_withdraw_limit}'
            )

            payload = json.dumps({
                'purchase_limit': purchase_limit,
                'consigned_limit': consigned_limit,
                'global_withdraw_limit': global_withdraw_limit,
            })
        else:
            limite_cartao = float(contrato.limite_pre_aprovado)
            valor_disponivel_saque = float(contrato_cartao.valor_disponivel_saque)

            url = (
                f'{URL}/accounts/{id_conta}/limits?consigned_limit={limite_cartao}'
                f'&global_limit={limite_cartao}&global_withdraw_limit={valor_disponivel_saque}'
            )

            payload = json.dumps({
                'globalLimit': limite_cartao,
                'consigned_limit': limite_cartao,
                'global_withdraw_limit': valor_disponivel_saque,
            })

        headers = {'Authorization': auth, 'Content-Type': 'application/json'}

        response = requests.request('PATCH', url, headers=headers, data=payload)
        cria_limite_cartao_obj = json.loads(response.text)

        if response.status_code in {200, 202}:
            cria_limite_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                payload=cria_limite_cartao_obj,
                payload_envio=payload,
                nome_chamada='Criação de limite do cartão',
                codigo_retorno=response.status_code,
            )

            if produto_convenio.cartao_virtual:
                create_virtual_card(
                    auth,
                    id_conta,
                    cliente,
                    log_api,
                    id_cliente,
                    contrato,
                    user,
                    contrato_cartao,
                )
            else:
                cria_cartao_dock(
                    auth,
                    id_conta,
                    id_cliente,
                    cliente,
                    contrato,
                    log_api,
                    contrato_cartao,
                    user,
                    produto_convenio,
                )
        else:
            cria_limite_obj = RetornosDock.objects.create(
                log_api=log_api,
                payload=cria_limite_cartao_obj,
                payload_envio=payload,
                nome_chamada='Criação de limite do cartão',
                codigo_retorno=response.status_code,
            )
            raise Exception(
                'Erro ao criar limite do cartão - código de resposta não esperado.'
            )
    except Exception as e:
        logger.error(
            f'Dock - Erro ao criar limite do cartão, cliente {cliente.nu_cpf}: {e}',
            exc_info=True,
        )
        raise
    return cria_limite_obj


def consulta_dados_cartao(auth, id_cartao, cliente_cartao, log_api, id_cliente):
    url = f'{URL}/cartoes/{id_cartao}'
    headers = {'Authorization': auth, 'Content-Type': 'application/json'}
    response = requests.request('GET', url, headers=headers)
    dados_consultados = json.loads(response.text)
    cliente_cartao.numero_cartao_dock = dados_consultados['numeroCartao']
    cliente_cartao.nome_impresso_dock = dados_consultados['nomeImpresso']
    cliente_cartao.save()

    RetornosDock.objects.create(
        log_api=log_api,
        id_cliente=id_cliente,
        payload=url,
        payload_envio=dados_consultados,
        nome_chamada='Consulta dados do Cartão',
        codigo_retorno=response.status_code,
    )


def cria_cartao_dock(
    auth,
    id_conta,
    id_cliente,
    cliente,
    contrato,
    log_api,
    contrato_cartao,
    user,
    produto_convenio,
):
    cria_cartao_dock_obj = {}
    try:
        url = f'{URL}/contas/{id_conta}/gerar-cartao-grafica'

        payload = json.dumps({
            'id_pessoa': id_cliente,
            'id_tipo_plastico': produto_convenio.id_plastico_dock,
            'idImagem': produto_convenio.id_imagem_dock,
        })
        headers = {'Authorization': auth, 'Content-Type': 'application/json'}
        response = requests.request('POST', url, headers=headers, data=payload)
        cria_cartao_obj = json.loads(response.text)

        if response.status_code in {200, 202}:
            cria_cartao_dock_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                payload=cria_cartao_obj,
                payload_envio=payload,
                nome_chamada='Criação do cartão',
                codigo_retorno=response.status_code,
            )

            cliente_cartao = contrato.cliente_cartao_contrato.get()
            cliente_cartao.id_cartao_dock = cria_cartao_obj['idCartao']
            cliente_cartao.save()
            contrato.status = EnumContratoStatus.PAGO
            contrato_cartao.status = ContractStatus.ANDAMENTO_EMISSAO_CARTAO.value
            contrato_cartao.tipo_cartao = 'Cartão Físico'
            contrato_cartao.save()
            contrato.save()
            user = UserProfile.objects.get(identifier=user.identifier)
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.ANDAMENTO_EMISSAO_CARTAO.value,
                created_by=user,
            )
            consulta_dados_cartao(
                auth, cliente_cartao.id_cartao_dock, cliente_cartao, log_api, id_cliente
            )
            cria_senha_cartao_dock(auth, id_conta, id_cliente, cliente, contrato)
        else:
            cria_cartao_dock_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                payload=cria_cartao_obj,
                payload_envio=payload,
                nome_chamada='Criação do cartão',
                codigo_retorno=response.status_code,
            )
            contrato.status = ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
            user = UserProfile.objects.get(identifier=user.identifier)
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                created_by=user,
            )
            contrato.save()
            raise Exception('Erro ao criar cartão - código de resposta não esperado.')
    except Exception as e:
        logger.error(
            f'Dock - Erro ao criar cartão, cliente {cliente.nu_cpf}: {e}',
            exc_info=True,
        )
        raise
    return cria_cartao_dock_obj


def create_virtual_card(
    auth, id_conta, cliente, log_api, id_cliente, contrato, user, contrato_cartao
):
    try:
        url = f'{URL}/contas/{id_conta}/gerar-cartao-virtual'
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': auth,
        }
        # Obtém a data atual
        today = datetime.utcnow().date()

        # Cria um datetime com a hora fixada em 00:00:00.000
        fixed_time_datetime = datetime.combine(today, datetime.min.time())

        # Adiciona 8 anos à data
        eight_years_later = fixed_time_datetime + relativedelta(years=8)

        # Formata a data e hora para o formato desejado
        formatted_date = eight_years_later.strftime('%Y-%m-%dT00:00:00.000Z')

        querystring = {'dataValidade': f'{formatted_date}'}

        response = requests.post(url, headers=headers, params=querystring)
        cria_cartao_obj = json.loads(response.text)
        if response.status_code in {200, 202}:
            cria_cartao_dock_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                payload=cria_cartao_obj,
                payload_envio=querystring,
                nome_chamada='Criação do cartão virtual',
                codigo_retorno=response.status_code,
            )

            cliente_cartao = contrato.cliente_cartao_contrato.get()
            cliente_cartao.id_cartao_dock = cria_cartao_obj['idCartao']
            contrato_cartao.tipo_cartao = 'Cartão Virtual'
            cliente_cartao.save()
            contrato_cartao.save()

            alterar_status(
                contrato,
                contrato_cartao,
                EnumContratoStatus.PAGO,
                ContractStatus.ANDAMENTO_EMISSAO_CARTAO.value,
                user,
            )

            cria_senha_cartao_dock(auth, id_conta, id_cliente, cliente, contrato)
        else:
            cria_cartao_dock_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                payload=cria_cartao_obj,
                payload_envio=querystring,
                nome_chamada='Criação do cartão',
                codigo_retorno=response.status_code,
            )
            alterar_status(
                contrato,
                contrato_cartao,
                EnumContratoStatus.MESA,
                ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                user,
            )
            raise Exception(
                'Erro ao criar cartão virutal - código de resposta não esperado.'
            )
        return cria_cartao_dock_obj
    except Exception as e:
        logger.error(
            f'Dock - Erro ao criar cartão virtual, cliente {cliente.nu_cpf}: {e}',
            exc_info=True,
        )
        raise


def cria_senha_cartao_dock(auth, id_conta, id_cliente, cliente, contrato):
    random_obj = {}
    try:
        import random

        random = str(random.randint(1000, 9999))

        url = f'{URL}/cartoes/{id_conta}/cadastrar-senha'

        payload = json.dumps({})
        headers = {
            'Authorization': auth,
            'senha': random,
            'Content-Type': 'application/json',
        }

        response = requests.request('POST', url, headers=headers, data=payload)
        if response.status_code == 200:
            random_obj = {response.text}

    except Exception as e:
        print(e)
    return random_obj
