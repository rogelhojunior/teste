# API de consultar a matricula na facil
import json
import logging
from datetime import datetime

import requests
import xmltodict
from django.conf import settings

from api_log.models import (
    Averbacao,
    CancelaReserva,
    ConsultaAverbadora,
    ConsultaConsignacoes,
    LogCliente,
    RealizaReserva,
)
from contract.constants import EnumTipoMargem
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.models.convenio import SubOrgao
from core.models import ParametrosBackoffice
from core.utils import consulta_cliente, get_dados_convenio

# TODO: Remover link de cada arquivo de averbadora, deixar o acesso mais 'global'

url = settings.HUB_AVERBADORA_URL

logger = logging.getLogger('digitacao')


def senha_backoffice():
    try:
        parametros = ParametrosBackoffice.objects.filter(ativo=True).first()
        senha_admin = parametros.senha_admin
        return senha_admin
    except Exception as e:
        logger.error(f'Erro ao consultar a senha backoffice: {e}', exc_info=True)
        return None


def consulta_matricula(numero_cpf, averbadora, codigo_convenio, numero_matricula):
    (
        senha_admin,
        usuario_convenio,
        _,
        url_convenio,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    payload = json.dumps(
        {
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'consultarMatricula',
            },
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'url': f'{url_convenio}',
            },
            'cliente': {'nuCpf': f'{numero_cpf}'},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {'Content-Type': 'application/json'}
    response = requests.request('POST', url, headers=headers, data=payload)
    response_data = response.json()

    if 'error' in response_data:
        return [], 'Erro_Consulta'

    try:
        filtered_response_data = [
            item
            for item in response_data
            if item['numeroMatricula'] == numero_matricula
        ]
    except Exception as e:
        logger.error(f'Erro ao filtrar a resposta da API: {e}', exc_info=True)
        return [], 'Erro_Filtrar'

    if not filtered_response_data:
        logger.warning(
            f'Não foi encontrado margem para a matrícula solicitada {numero_matricula}.'
        )
        return [], 'Erro_Matricula_Nao_Encontrada'

    if 'error' in filtered_response_data:
        logger.warning(
            f'Não foi possível consultar a matrícula para o servidor {numero_cpf}',
            exc_info=True,
        )
        return [], 'Erro_Consulta'

    valid_matriculas_data = []
    active_consignations = False

    try:
        suborgaos = SubOrgao.objects.filter(convenio=convenios, ativo=True)
        if not suborgaos.exists():
            return [], 'SubOrgao_Vazio'

        # Liste os códigos de folha ativos
        active_folha_codes = [suborgao.codigo_folha for suborgao in suborgaos]

        for matricula in filtered_response_data:
            if matricula['folha'] in active_folha_codes:
                consignacoes = consulta_consignacoes(
                    numero_cpf,
                    averbadora,
                    codigo_convenio,
                    matricula['numeroMatricula'],
                    matricula['folha'],
                )
                # If consignacoes is a structure with a 'descricao' attribute, check it
                if (
                    hasattr(consignacoes, 'descricao')
                    and consignacoes.descricao is None
                    and consignacoes.valor
                ):
                    active_consignations = True
                    break  # Break out of the loop as we found active consignation
                else:
                    valid_matriculas_data.append(matricula)

        if active_consignations:
            return [], 'Consignacao_Ativa'

        if not valid_matriculas_data:
            return [], 'Matriculas_Invalidas'

    except Exception as e:
        logger.error(str(e), exc_info=True)
        return [], 'Erro_Consulta'

    return valid_matriculas_data, None


def save_consignacao(response_dic, cliente):
    valor = response_dic['valor']
    valor_liberado = response_dic['valor_liberado']
    codigo_operacao_instituicao = response_dic['codigo_operacao_instituicao']
    verba = response_dic['verba']
    prazo_restante = response_dic['prazo_restante']
    data_consignacao = response_dic['data_consignacao']

    if data_consignacao:
        data_consignacao = datetime.strptime(
            data_consignacao, '%d/%m/%Y %H:%M:%S'
        ).strftime('%Y-%m-%d %H:%M:%S')
    codigo_operacao = response_dic['codigo_operacao']

    consignacao_obj, _ = ConsultaConsignacoes.objects.get_or_create(
        cliente=cliente,
        codigo_operacao=codigo_operacao,
        valor=valor,
        valor_liberado=valor_liberado,
        codigo_operacao_instituicao=codigo_operacao_instituicao,
        verba=verba,
        prazo_restante=prazo_restante,
        data_consignacao=data_consignacao,
    )
    return consignacao_obj


def consulta_consignacoes(
    numero_cpf, averbadora, codigo_convenio, numero_matricula, folha
):
    # Obtendo os dados do convênio
    senha_admin, usuario_convenio, _, url_convenio, _ = get_dados_convenio(
        averbadora, codigo_convenio
    )

    # Criando o payload para a requisição
    payload = json.dumps({
        'averbadora': {
            'nomeAverbadora': averbadora,
            'operacao': 'consultarConsignacoes',
        },
        'parametrosBackoffice': {
            'senhaAdmin': senha_admin,
            'usuario': usuario_convenio,
            'url': url_convenio,
        },
        'cliente': {
            'nuCpf': numero_cpf,
            'nuFolha': folha,
            'nuMatricula': numero_matricula,
        },
    })

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.post(
        url, headers=headers, data=payload
    )  # Usar diretamente o método POST
    response_text = response.json()  # Conversão direta para json

    return (
        {
            'descricao': response_text['descricao'],
            'codigo_retorno': response_text['codigoRetorno'],
        }
        if 'descricao' in response_text
        else {
            'codigo_operacao': response_text['codigoOperacao'],
            'valor': response_text['valor'],
            'valor_liberado': response_text['valorLiberado'],
            'codigo_operacao_instituicao': response_text['codigoOperacaoInstituicao'],
            'verba': response_text['verba'],
            'prazo_restante': response_text['prazoRestante'],
            'data_consignacao': response_text['dataConsignacao'],
        }
    )


# API de consulta de margem na facil
# Função em desuso
# def consulta_margem(
#     numero_cpf, averbadora, codigo_convenio, numero_matricula, folha, verba
# ):
#     (
#         senha_admin,
#         usuario_convenio,
#         verba_convenio,
#         url_convenio,
#         convenios,
#     ) = get_dados_convenio(averbadora, codigo_convenio)
#
#     cliente = consulta_cliente(numero_cpf)
#
#     payload = json.dumps(
#         {
#             'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'consultarMargem'},
#             'parametrosBackoffice': {
#                 'senhaAdmin': f'{senha_admin}',
#                 'usuario': f'{usuario_convenio}',
#                 'url': f'{url_convenio}',
#             },
#             'cliente': {
#                 'nuCpf': f'{numero_cpf}',
#                 'nuMatricula': f'{numero_matricula}',
#                 'nuFolha': f'{folha}',
#                 'verba': f'{verba}',
#             },
#         },
#         indent=4,
#         ensure_ascii=False,
#     )
#
#     headers = {
#         'Content-Type': 'application/json',
#     }
#     response = requests.request('POST', url, headers=headers, data=payload)
#     response_text = json.loads(response.text)
#
#     log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
#
#     # Trate erros primeiro
#     if 'descricao' in response_text:
#         margem_obj = ConsultaMargem.objects.create(
#             log_api_id=log_api_id.pk,
#             cliente=cliente,
#             descricao=response_text['descricao'],
#             codigo_retorno=response_text['codigoRetorno'],
#         )
#         ConsultaAverbadora.objects.create(
#             log_api_id=log_api_id.pk,
#             cliente=cliente,
#             payload_envio=payload,
#             payload=response_text,
#             tipo_chamada='Consulta Margem',
#         )
#         return margem_obj
#
#     # Tratar caso bem-sucedido
#     try:
#         cliente_cartao_beneficio, _ = ClienteCartaoBeneficio.objects.get_or_create(
#             cliente=cliente,
#             defaults={
#                 'convenio': convenios,
#             },
#         )
#         cliente_cartao_beneficio.convenio = convenios
#         cliente_cartao_beneficio.margem_atual = response_text.get(
#             'margemAtual', cliente_cartao_beneficio.margem_atual
#         )
#         cliente_cartao_beneficio.verba = response_text.get(
#             'verba', cliente_cartao_beneficio.verba
#         )
#         cliente_cartao_beneficio.folha = response_text.get(
#             'folha', cliente_cartao_beneficio.folha
#         )
#         cliente_cartao_beneficio.numero_matricula = response_text.get(
#             'numeroMatricula', cliente_cartao_beneficio.numero_matricula
#         )
#         cliente_cartao_beneficio.save()
#
#         cliente.nome_cliente = response_text.get('nome', cliente.nome_cliente)
#         cliente.save()
#
#         try:
#             margem_obj, _ = ConsultaMargem.objects.update_or_create(
#                 log_api_id=log_api_id.pk,
#                 cliente=cliente,
#                 defaults={
#                     'matricula': response_text['numeroMatricula'],
#                     'folha': response_text['folha'],
#                     'verba': response_text['verba'],
#                     'margem_atual': response_text['margemAtual'],
#                     'cargo': response_text.get('cargo'),
#                     'estavel': response_text.get('estavel'),
#                 },
#             )
#         except ConsultaMargem.MultipleObjectsReturned:
#             handle_multiple_objects(
#                 ConsultaMargem, log_api_id=log_api_id.pk, cliente=cliente
#             )
#             margem_obj, _ = ConsultaMargem.objects.update_or_create(
#                 log_api_id=log_api_id.pk,
#                 cliente=cliente,
#                 defaults={
#                     'matricula': response_text['numeroMatricula'],
#                     'folha': response_text['folha'],
#                     'verba': response_text['verba'],
#                     'margem_atual': response_text['margemAtual'],
#                     'cargo': response_text.get('cargo'),
#                     'estavel': response_text.get('estavel'),
#                 },
#             )
#
#         logger.info(
#             f'{cliente.id_unico} - Margem consultada na averbadora {averbadora}'
#         )
#     except Exception as e:
#         logger.error(
#             f'{cliente.id_unico} - Erro ao consultar margem na averbadora {averbadora}: {e}',
#             exc_info=True,
#         )
#
#     ConsultaAverbadora.objects.create(
#         log_api_id=log_api_id.pk,
#         cliente=cliente,
#         payload_envio=payload,
#         payload=response_text,
#         tipo_chamada='Consulta Margem',
#     )
#     return margem_obj


# API QUE REALIZA RESERVA DA MARGEM NA FACIL
def realiza_reserva(numero_cpf, averbadora, codigo_convenio, contrato):
    try:
        (
            senha_admin,
            usuario_convenio,
            _,
            url_convenio,
            _,
        ) = get_dados_convenio(averbadora, codigo_convenio)

        cliente = consulta_cliente(numero_cpf)
        cliente_cartao_beneficio = contrato.cliente_cartao_contrato.get()
        if cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
            valor = cliente_cartao_beneficio.margem_compra
            verba = cliente_cartao_beneficio.verba_compra
            folha = cliente_cartao_beneficio.folha_compra
        elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
            valor = cliente_cartao_beneficio.margem_saque
            verba = cliente_cartao_beneficio.verba_saque
            folha = cliente_cartao_beneficio.folha_saque
        elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_UNICA:
            valor = cliente_cartao_beneficio.margem_atual
            verba = cliente_cartao_beneficio.verba
            folha = cliente_cartao_beneficio.folha
        matricula = cliente_cartao_beneficio.numero_matricula
    except Exception as e:
        logger.error(
            f'Erro buscar informações para realizar reserva de margem na facil: {e}',
            exc_info=True,
        )
        return

    if cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
        margens_a_reservar = {
            'compra': {
                'valor': cliente_cartao_beneficio.margem_compra,
                'verba': cliente_cartao_beneficio.verba_compra,
                'folha': cliente_cartao_beneficio.folha_compra,
            },
            'saque': {
                'valor': cliente_cartao_beneficio.margem_saque,
                'verba': cliente_cartao_beneficio.verba_saque,
                'folha': cliente_cartao_beneficio.folha_saque,
            },
        }
        margens_reservadas = []

        for tipo_margem, dados_margem in margens_a_reservar.items():
            payload = json.dumps(
                {
                    'averbadora': {
                        'nomeAverbadora': averbadora,
                        'operacao': 'realizarReserva',
                    },
                    'parametrosBackoffice': {
                        'senhaAdmin': senha_admin,
                        'usuario': usuario_convenio,
                        'url': url_convenio,
                    },
                    'cliente': {
                        'nuCpf': numero_cpf,
                        'nuMatricula': matricula,
                        'nuFolha': dados_margem['folha'],
                        'verba': dados_margem['verba'],
                        'valor': float(dados_margem['valor']),
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
                if tipo_margem == 'compra':
                    cliente_cartao_beneficio.reserva_compra = response_text['reserva']
                elif tipo_margem == 'saque':
                    cliente_cartao_beneficio.reserva_saque = response_text['reserva']
                cliente_cartao_beneficio.save()
                realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    matricula=response_text['numeroMatricula'],
                    folha=response_text['folha'],
                    verba=dados_margem['verba'],
                    valor=response_text['valor'],
                    reserva=response_text['reserva'],
                )
                margens_reservadas.append(tipo_margem)
            except Exception as e:
                print(e)
                realiza_reserva_obj = RealizaReserva.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    descricao=response_text['descricao'],
                    codigo_retorno=response_text['codigoRetorno'],
                )
                for margem_reservada in margens_reservadas:
                    cancela_reserva(
                        numero_cpf,
                        matricula,
                        averbadora,
                        codigo_convenio,
                        contrato.pk,
                        margem_reservada,
                    )
            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                payload_envio=payload,
                payload=response_text,
                tipo_chamada='Realiza Reserva',
            )
    else:
        payload = json.dumps(
            {
                'averbadora': {
                    'nomeAverbadora': averbadora,
                    'operacao': 'realizarReserva',
                },
                'parametrosBackoffice': {
                    'senhaAdmin': f'{senha_admin}',
                    'usuario': f'{usuario_convenio}',
                    'url': f'{url_convenio}',
                },
                'cliente': {
                    'nuCpf': f'{numero_cpf}',
                    'nuMatricula': f'{matricula}',
                    'nuFolha': f'{folha}',
                    'verba': f'{verba}',
                    'valor': f'{valor}',
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
            if cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
                cliente_cartao_beneficio.reserva_compra = response_text['reserva']
            elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
                cliente_cartao_beneficio.reserva_saque = response_text['reserva']
            else:
                cliente_cartao_beneficio.reserva = response_text['reserva']
            cliente_cartao_beneficio.save()

            realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                matricula=response_text['numeroMatricula'],
                folha=response_text['folha'],
                verba=verba,
                valor=response_text['valor'],
                reserva=response_text['reserva'],
            )
        except Exception as e:
            print(e)
            realiza_reserva_obj = RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_text['descricao'],
                codigo_retorno=response_text['codigoRetorno'],
            )
        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            payload_envio=payload,
            payload=response_text,
            tipo_chamada='Realiza Reserva',
        )
    return realiza_reserva_obj


def cancela_reserva(
    numero_cpf,
    numero_matricula,
    averbadora,
    codigo_convenio,
    contrato,
    margem_reservada=None,
):
    (
        senha_admin,
        usuario_convenio,
        _,
        url_convenio,
        _,
    ) = get_dados_convenio(averbadora, codigo_convenio)
    contrato = Contrato.objects.get(pk=contrato)
    cliente = consulta_cliente(numero_cpf)
    cliente_cartao_beneficio = contrato.cliente_cartao_contrato.get()

    folha = cliente_cartao_beneficio.folha
    reserva = cliente_cartao_beneficio.reserva

    if margem_reservada == 'compra':
        folha = cliente_cartao_beneficio.folha_compra
        reserva = cliente_cartao_beneficio.reserva_compra
    elif margem_reservada == 'saque':
        folha = cliente_cartao_beneficio.folha_saque
        reserva = cliente_cartao_beneficio.reserva_saque

    if (
        margem_reservada is None
        and cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA
    ):
        margens_a_reservar = {
            'compra': {
                'folha': cliente_cartao_beneficio.folha_compra,
                'reserva': cliente_cartao_beneficio.reserva_compra,
            },
            'saque': {
                'folha': cliente_cartao_beneficio.folha_saque,
                'reserva': cliente_cartao_beneficio.reserva_saque,
            },
        }
        for dados_margem in margens_a_reservar.values():
            payload = json.dumps(
                {
                    'averbadora': {
                        'nomeAverbadora': averbadora,
                        'operacao': 'cancelarReserva',
                    },
                    'parametrosBackoffice': {
                        'senhaAdmin': f'{senha_admin}',
                        'usuario': f'{usuario_convenio}',
                        'url': f'{url_convenio}',
                    },
                    'cliente': {
                        'nuCpf': f'{numero_cpf}',
                        'nuMatricula': f'{numero_matricula}',
                        'nuFolha': dados_margem['folha'],
                        'nuReserva': dados_margem['reserva'],
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
                print(e)
                cancela_reserva_obj = CancelaReserva.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    descricao=response_text['descricao'],
                    codigo_retorno=response_text['codigoRetorno'],
                )
            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                payload_envio=payload,
                payload=response_text,
                tipo_chamada='Cancela Reserva',
            )
        return cancela_reserva_obj

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'cancelarReserva'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'url': f'{url_convenio}',
            },
            'cliente': {
                'nuCpf': f'{numero_cpf}',
                'nuMatricula': f'{numero_matricula}',
                'nuFolha': f'{folha}',
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
        print(e)
        cancela_reserva_obj = CancelaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )
    ConsultaAverbadora.objects.create(
        log_api_id=log_api_id.pk,
        cliente=cliente,
        payload_envio=payload,
        payload=response_text,
        tipo_chamada='Cancela Reserva',
    )
    return cancela_reserva_obj


# API de Averbação
# NÃO ESTÁ SENDO USADA
def averbacao(numero_cpf, numero_matricula, valor_parcela, contrato):
    parcelas = 1
    cliente = consulta_cliente(numero_cpf)
    reserva = cliente.reserva
    contrato.reserva = reserva
    codigo_instituicao = str(contrato.codigo_instituicao)
    verba = cliente.verba
    folha = cliente.folha
    valor_liberado = cliente.margem_atual
    resp_error = False

    parametros = ParametrosBackoffice.objects.filter(ativo=True).first()

    senha_admin = parametros.senha_admin

    id = 1

    url = 'https://www.faciltecnologia.com.br/consigfacil/teste_integrador/integrador_wsdl.php'

    payload = (
        f'transacao=%3Ctransacoes%3E%0A%3Ctransacao%20type%3D%22AVERBACAO%22%3E%0A%3Cid%3E{id}%3C%2Fid%3E%0A%3C'
        f'login%3EINTEGCONSIG%3C%2Flogin%3E%0A%3Csenha%3E{senha_admin}%3C%2Fsenha%3E%0A%3Cmatricula%3E{numero_matricula}%3C%2F'
        f'matricula%3E%0A%3Ccpf%3E{numero_cpf}%3C%2Fcpf%3E%0A%3Cfolha%3E{folha}%3C%2Ffolha%3E%0A%3Cparcelas%3E{parcelas}%3C%2F'
        f'parcelas%3E%0A%3Cvalor_parcela%3E{valor_parcela}%3C%2Fvalor_parcela%3E%0A%3Cvalor_liberado%3E{valor_liberado}%3C%2Fvalor_liberado'
        f'%3E%0A%3Cverba%3E{verba}%3C%2Fverba%3E%0A%3Ccodigo_instituicao%3E{codigo_instituicao}%3C%2F'
        f'codigo_instituicao%3E%0A%3C%2Ftransacao%3E%0A%3C%2Ftransacoes%3E'
    )
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'ConsigFacilconsigfacil=7mfcah36imjoajr7269i4tla04',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = response.text
    response_dic = xmltodict.parse(response_text)

    try:
        response_dic = response_dic['retorno']['transacao']
        numero_matricula = response_dic['matricula']
        verba = response_dic['verba']
        folha = response_dic['folha']
        valor = response_dic['valor']
        contrato_facil = response_dic['contrato']

        contrato_save = contrato
        contrato_save.numero_contrato_facil = contrato_facil
        contrato_save.reserva = reserva
        contrato_save.verba = verba
        contrato_save.numero_matricula = numero_matricula
        contrato_save.folha = folha
        contrato_save.save()

        Averbacao.objects.create(
            cliente=cliente,
            verba=verba,
            folha=folha,
            matricula=numero_matricula,
            valor=valor,
            contrato=contrato_facil,
        )

    except Exception as e:
        print(e)
        resp_error = True
        response_dic = response_dic['erro']
        codigo_retorno = response_dic['codigo']
        descricao = response_dic['descricao']
        Averbacao.objects.create(
            cliente=cliente, descricao=descricao, codigo_retorno=codigo_retorno
        )
    return resp_error
