import json
import logging
from datetime import datetime

import requests
from django.conf import settings

from api_log.models import (
    CancelaReserva,
    ConsultaConsignacoes,
    ConsultaMargem,
    ConsultaMatricula,
    LogCliente,
    RealizaReserva,
)
from core.models.cliente import ClienteCartaoBeneficio
from core.utils import consulta_cliente, get_dados_convenio

# TODO: Remover link de cada arquivo de averbadora, deixar o acesso mais 'global'

url = settings.HUB_AVERBADORA_URL


logger = logging.getLogger('digitacao')


# API de consulta de margem na quantum
def consulta_consignacoes_quantum(numero_cpf, averbadora, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)

    # TODO: Remover convênio fixo
    payload = json.dumps(
        {
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'consultarConsignacao',
            },
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': '10',
            },
            'cliente': {'nuCpf': f'{numero_cpf}'},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    try:
        consignacao_obj = ConsultaConsignacoes.objects.get_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=200,
        )
    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao consultar consignações {averbadora}. {e}',
            exc_info=True,
        )

        consignacao_obj = ConsultaConsignacoes.objects.get_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=200,
        )

    return consignacao_obj


def consulta_martricula_quantum(numero_cpf, averbadora, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    matricula_obj = None

    # TODO: Remover convênio fixo
    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'consultarMargem'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': '10',
            },
            'cliente': {'nuCpf': f'{numero_cpf}'},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)

    cliente = consulta_cliente(numero_cpf)

    try:
        response_text = json.loads(response.text)
        if nascimento := response_text['nascimento']:
            nascimento = datetime.strptime(nascimento, '%d/%m/%Y').strftime('%Y-%m-%d')
            cliente.dt_nascimento = nascimento
            cliente.nome_cliente = response_text['nome']
            cliente.save()

            ClienteCartaoBeneficio.objects.update_or_create(
                cliente=cliente,
                numero_matricula=response_text['numeroMatricula'],
                folha=response_text['folha'],
                verba=response_text['verba'],
                margem_atual=response_text['margemAtual'],
            )
        else:
            # cliente.data_nascimento = response_text['nascimento']
            cliente.nome_cliente = f"{response_text['nome']} - quantum"
            ClienteCartaoBeneficio.objects.update_or_create(
                cliente=cliente,
                numero_matricula=response_text['numeroMatricula'],
                folha=response_text['folha'],
                verba=response_text['verba'],
                margem_atual=response_text['margemAtual'],
            )
            cliente.save()

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        matricula_obj, _ = ConsultaMatricula.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=response_text['numeroMatricula'],
            folha=response_text['folha'],
            verba=response_text['verba'],
            margem_atual=response_text['margemAtual'],
            cargo=response_text['cargo'],
            estavel=response_text['estavel'],
        )

    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao matrícula margem {averbadora}. {e}',
            exc_info=True,
        )
    return matricula_obj


def consulta_margem_quantum(numero_cpf, averbadora, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)
    cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.get(cliente=cliente)

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'consultarMargem'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': '10',
            },
            'cliente': {'nuCpf': f'{numero_cpf}'},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)

    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
    try:
        cliente_cartao_beneficio.margem_atual = response_text['margemAtual']
        cliente_cartao_beneficio.verba = response_text['verba']
        cliente_cartao_beneficio.folha = response_text['folha']
        cliente_cartao_beneficio.numero_matricula = response_text['numeroMatricula']
        cliente_cartao_beneficio.save()

        margem_obj, _ = ConsultaMargem.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=response_text['numeroMatricula'],
            folha=response_text['folha'],
            verba=response_text['verba'],
            margem_atual=response_text['margemAtual'],
            cargo=response_text['cargo'],
            estavel=response_text['estavel'],
        )

        logger.error(
            f'{cliente.id_unico} - Margem consultada {averbadora}.', exc_info=True
        )
    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao consultar margem {averbadora}. {e}',
            exc_info=True,
        )

        margem_obj = ConsultaMargem.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )
    return margem_obj


def reservar_margem_quantum(numero_cpf, averbadora, valor, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)
    margem = cliente.margem_atual

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'reservarMargem'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': '10',
            },
            'cliente': {
                'nuCpf': f'{numero_cpf}',
                'valParcela': f'{valor}',
                'nuMatricula': f'{cliente.numero_matricula}',
                'valLiberado': f'{margem}',
            },
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)

    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    try:
        numero_matricula = response_text['numeroMatricula']
        verba = response_text['verba']
        folha = response_text['folha']
        valor = response_text['valor']
        reserva = response_text['reserva']

        ClienteCartaoBeneficio.objects.update_or_create(
            cliente=cliente,
            numero_matricula=response_text['numeroMatricula'],
            folha=response_text['folha'],
            verba=response_text['verba'],
            margem_atual=response_text['margemAtual'],
            reserva=reserva,
        )
        realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=numero_matricula,
            folha=folha,
            verba=verba,
            valor=valor,
            reserva=reserva,
        )
    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao reservar margem {averbadora}. {e}',
            exc_info=True,
        )
        realiza_reserva_obj = RealizaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )
    return realiza_reserva_obj


def cancela_reserva_quantum(numero_cpf, averbadora, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)
    cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.get(cliente=cliente)
    reserva = cliente_cartao_beneficio.reserva

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': 3, 'operacao': 'cancelarConsignacao'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': '10',
            },
            'cliente': {
                'nuCpf': f'{numero_cpf}',
                'nuMatricula': f'{cliente.numero_matricula}',
                'nuReserva': f'{reserva}',
            },
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)

    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
    try:
        numero_matricula = response_text['numeroMatricula']
        reserva = response_text['reserva']
        cancelada = response_text['cancelada']

        cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=numero_matricula,
            reserva=reserva,
            cancelada=cancelada,
        )
    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao cancelar reserva {averbadora}. {e}',
            exc_info=True,
        )
        cancela_reserva_obj = CancelaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )
    return cancela_reserva_obj
