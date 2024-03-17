import json
import re
from datetime import datetime

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from api_log.models import LogCliente, RetornosDock
from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    RetornoSaque,
    SaqueComplementar,
)
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    ProdutoConvenio,
)
from core.models.cliente import DadosBancarios
from core.utils import alterar_status, consulta_cliente
from custom_auth.models import UserProfile
from handlers.dock_cartao import cria_limte_cartao
from handlers.email import enviar_email

logger = get_task_logger('cliente')

# TODO: Credenciais não podem estar no mesmo banco de dados da aplicação -> exigência dock
url_token = settings.DOCK_URL_TOKEN
url_base = settings.DOCK_URL_BASE
client_id = settings.DOCK_CLIENT_ID
client_password = settings.DOCK_CLIENT_PASSWORD


def gerar_token(client_id, client_password):
    # Obtem o token de acesso para as demais APIs
    auth = ''
    url = f'{url_token}/oauth2/token'
    querystring = {'grant_type': 'client_credentials'}

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.request(
            'POST',
            url,
            headers=headers,
            params=querystring,
            auth=(client_id, client_password),
        )
        logger.info('status code response', response.status_code)
        if response.status_code == 200:
            credenciais_obj = json.loads(response.text)
            auth = credenciais_obj['access_token']
        else:
            logger.info(
                f'Dock - Falha ao gerar token, status code: {response.status_code}'
            )

    except Exception as e:
        print(e)
        logger.error('Dock - Erro ao gerar token', exc_info=True)

    return auth


@shared_task
def criar_individuo_dock(self, numero_cpf, contrato_pk, user, nome_convenio):
    from handlers.contrato import processa_contrato

    auth = gerar_token(client_id, client_password)
    cria_individuo_obj = {}
    url = f'{url_base}/v2/individuals'
    user = UserProfile.objects.get(identifier=user)

    cliente = consulta_cliente(numero_cpf)
    try:
        nome_cliente = cliente.nome_cliente
        nome_mae = cliente.nome_mae
        data_nasc = cliente.dt_nascimento
        data_nasc = str(data_nasc)
        telefone_celular = cliente.telefone_celular
        endereco_cep = cliente.endereco_cep

        try:
            numero_cpf = numero_cpf.replace('.', '').replace('-', '')
        except Exception as e:
            logger.error(
                f'Erro ao formatar cpf (criar_individuo_dock): {e}', exc_info=True
            )

        try:
            numero_cliente = re.sub(r'\D', '', telefone_celular)
            if numero_cliente.startswith('0'):
                ddd_cliente = numero_cliente[1:3]
                numero_cliente = numero_cliente[3:]
            else:
                ddd_cliente = numero_cliente[:2]
                numero_cliente = numero_cliente[2:]

            endereco_cep = cliente.endereco_cep.replace('-', '')
        except Exception as e:
            logger.error(
                f'Erro ao formatar dados cliente (criar_individuo_dock): {e}',
                exc_info=True,
            )

        try:
            data_nasc_convertida = data_nasc.split('/')
            data_nasc = f'{data_nasc_convertida[2]}-{data_nasc_convertida[1]}-{data_nasc_convertida[0]}'
        except Exception as e:
            print(e)
        # nu_documento = cliente.documento_numero
        # dock espera até 6 caracteres no máximo
        documento_emissor = cliente.documento_orgao_emissor[:6]
        documento_uf = cliente.get_documento_uf_display()
        data_documento = str(cliente.documento_data_emissao)
        pep = cliente.ppe
        email = cliente.email

        endereco = cliente.endereco_logradouro
        endereco_bairro = cliente.endereco_bairro
        endereco_numero = int(cliente.endereco_numero)
        endereco_cidade = cliente.endereco_cidade
        endereco_uf = cliente.endereco_uf
        endereco_complemento = cliente.endereco_complemento

        payload = json.dumps({
            'name': nome_cliente,
            'motherName': nome_mae,
            'birthDate': data_nasc,
            'document': numero_cpf,
            'identityIssuingEntity': documento_emissor,
            'federativeUnit': documento_uf,
            'issuingDateIdentity': data_documento,
            'email': email,
            'isPep': pep,
            'address': {
                'idAddressType': 1,
                'zipCode': endereco_cep,
                'street': endereco,
                'number': endereco_numero,
                'complement': endereco_complemento,
                'neighborhood': endereco_bairro,
                'city': endereco_cidade,
                'federativeUnit': endereco_uf,
                'country': 'Brasil',
                'mailingAddress': True,
            },
            'phone': {
                'idPhoneType': 1,
                'areaCode': f'0{ddd_cliente}',
                'number': numero_cliente,
            },
            'deviceIdentification': {'fingerprint': 'Dock'},
        })
        headers = {'Content-Type': 'application/json', 'Authorization': f'{auth}'}

        response = requests.request('POST', url, headers=headers, data=payload)
        individuo_conta_obj = json.loads(response.text)
        log_api = LogCliente.objects.get(cliente=cliente)
        contrato = Contrato.objects.get(pk=contrato_pk)
        contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)

        if response.status_code in {200, 202}:
            print('Payload', payload)
            print('Hearder', headers)
            print('resposta DOCK', individuo_conta_obj)
            id_cliente = individuo_conta_obj['id']
            status_registro = individuo_conta_obj['status']
            id_endereco = individuo_conta_obj['address']['id']
            id_telefone = individuo_conta_obj['phone']['id']

            cria_individuo_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                cliente=cliente,
                payload=individuo_conta_obj,
                payload_envio=payload,
                nome_chamada='Criação de indivíduo',
                codigo_retorno=response.status_code,
            )
            cliente_cartao = contrato.cliente_cartao_contrato.get()

            cliente_cartao.id_registro_dock = id_cliente
            cliente_cartao.id_endereco_dock = id_endereco
            cliente_cartao.id_telefone_dock = id_telefone
            cliente_cartao.status_dock = status_registro
            cliente_cartao.save()
            cliente.save()
            atualizar_telefone_dock(cliente, cliente_cartao)
            criar_conta_dock(
                cliente,
                auth,
                id_endereco,
                contrato,
                cliente_cartao,
                contrato_cartao,
                log_api,
                user,
            )
            alterar_status(
                contrato,
                contrato_cartao,
                EnumContratoStatus.PAGO,
                ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                user,
            )
        else:
            cria_individuo_obj = RetornosDock.objects.create(
                log_api=log_api,
                cliente=cliente,
                payload=individuo_conta_obj,
                payload_envio=payload,
                nome_chamada='Criação de indivíduo',
                codigo_retorno=response.status_code,
            )
            contrato_cartao.status = ContractStatus.ERRO_CRIACAO_CARTAO.value
            contrato.status = EnumContratoStatus.ERRO
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.ERRO_CRIACAO_CARTAO.value,
                created_by=user,
            )
            contrato_cartao.save()
            contrato.save()
            logger.error(
                f'Dock - Erro ao criar indivíduo, cliente {cliente.nu_cpf}: {individuo_conta_obj}',
                exc_info=True,
            )
            raise Exception(
                'Erro ao criar indivíduo - código de resposta não esperado.'
            )

        processa_contrato(contrato, contrato_cartao, cliente, cliente_cartao, user)
    except Exception as e:
        logger.error(
            f'Dock - Erro ao criar indivíduo, cliente {cliente.nu_cpf}: {e}',
            exc_info=True,
        )
        raise
    return cria_individuo_obj


def criar_conta_dock(
    cliente, auth, id_endereco, contrato, cliente_cartao, contrato_cartao, log_api, user
):
    url = f'{url_base}/contas'
    cria_conta_obj = {}
    try:
        cartao_beneficio_cliente = (
            contrato_cartao.contrato.cliente_cartao_contrato.get()
        )
        convenio = Convenios.objects.filter(
            pk=cartao_beneficio_cliente.convenio.pk
        ).first()
        produto_convenio = ProdutoConvenio.objects.filter(
            convenio=convenio, produto=contrato_cartao.contrato.tipo_produto
        ).first()
        id_cliente = cliente_cartao.id_registro_dock
        try:
            vencimento_fatura = int(contrato.vencimento_fatura)
        except Exception as e:
            logger.error(
                f'Erro ao formatar vencimento_fatura (criar_conta_dock): {e}',
                exc_info=True,
            )
            vencimento_fatura = 10

        payload = json.dumps({
            'idPessoa': id_cliente,
            'idOrigemComercial': produto_convenio.id_produto_logo_dock,
            'idProduto': produto_convenio.id_produto_logo_dock,
            'idEnderecoCorrespondencia': id_endereco,
            'diaVencimento': vencimento_fatura,
            'valorRenda': 0,
            'valorPontuacao': 0,
            'limiteParcelas': 1,
            'limiteConsignado': 1,
            'limiteMaximo': 10,
            'limiteGlobal': 12,
            'flagFaturaPorEmail': 1,
        })
        headers = {'Content-Type': 'application/json', 'Authorization': auth}

        response = requests.request('POST', url, headers=headers, data=payload)
        conta_obj = json.loads(response.text)

        if response.status_code in {200, 202}:
            id_conta = conta_obj['id']
            id_cliente = conta_obj['idPessoa']
            cria_conta_obj = RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=id_cliente,
                cliente=cliente,
                payload=conta_obj,
                payload_envio=payload,
                nome_chamada='Criação de conta',
                codigo_retorno=response.status_code,
            )

            cliente_cartao.id_conta_dock = id_conta
            cliente_cartao.save()
            cria_limte_cartao(
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
            )
        else:
            cria_conta_obj = RetornosDock.objects.create(
                log_api=log_api,
                payload=conta_obj,
                nome_chamada='Criação de conta',
                payload_envio=payload,
                codigo_retorno=response.status_code,
            )
            contrato_cartao.status = ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
            contrato.status = EnumContratoStatus.MESA
            user = UserProfile.objects.get(identifier=user.identifier)
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                created_by=user,
            )
            contrato_cartao.save()
            contrato.save()
            raise Exception('Erro ao criar conta - código de resposta não esperado.')
    except Exception as e:
        logger.error(
            f'Dock - Erro ao criar conta, cliente {cliente.nu_cpf}: {e}',
            exc_info=True,
        )
        raise

    return cria_conta_obj


# Consulta Conta Cartão na dock
# Sistema de logs Ja incluso na chamada
def consulta_conta_dock(cliente, contrato):
    auth = gerar_token(client_id, client_password)
    cliente_cartao = contrato.cliente_cartao_contrato.get()
    log_api = LogCliente.objects.get(cliente=cliente)
    account_obj = {}
    try:
        url = f'{url_base}/contas/{cliente_cartao.id_conta_dock}'

        headers = {'Content-Type': 'application/json', 'Authorization': auth}

        response = requests.request('GET', url, headers=headers)
        conta_obj = json.loads(response.text)
        if response.status_code == 200:
            RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=conta_obj,
                nome_chamada='Consultar Conta',
                codigo_retorno=response.status_code,
            )
            account_obj['idStatusConta'] = conta_obj['idStatusConta']
            account_obj['SaqueDisponivel'] = conta_obj['saldoDisponivelSaque']
            account_obj['ConsultaRealizada'] = True

        else:
            RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=conta_obj,
                nome_chamada='Consultar Conta',
                codigo_retorno=response.status_code,
            )
            account_obj['ConsultaRealizada'] = False
    except Exception as e:
        print(e)
        RetornosDock.objects.create(
            log_api=log_api,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Consultar Conta',
            codigo_retorno='400',
        )
        account_obj['ConsultaRealizada'] = False
        logger.error(
            f'Dock - Erro ao consultar conta, cliente {cliente.id_unico}', exc_info=True
        )
    return account_obj


# Consulta Cartão na dock
# Sistema de Log Ja incluso na chamada
def consulta_cartao_dock(cliente, contrato):
    auth = gerar_token(client_id, client_password)
    cliente_cartao = contrato.cliente_cartao_contrato.get()
    log_api = LogCliente.objects.get(cliente=cliente)

    card_obj = {}
    try:
        url = f'{url_base}/cartoes/{cliente_cartao.id_cartao_dock}'

        headers = {'Content-Type': 'application/json', 'Authorization': auth}

        response = requests.request('GET', url, headers=headers)
        cartao_obj = json.loads(response.text)
        if response.status_code == 200:
            RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=cartao_obj,
                nome_chamada='Consultar Cartao',
                codigo_retorno=response.status_code,
            )
            card_obj = cartao_obj['idStatusCartao']
        else:
            RetornosDock.objects.create(
                log_api=log_api,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=cartao_obj,
                nome_chamada='Consultar Cartao',
                codigo_retorno=response.status_code,
            )
            card_obj = 'error'
    except Exception as e:
        logger.error(
            f'Dock - Erro ao consultar cartão, cliente {cliente.id_unico}',
            exc_info=True,
        )
        RetornosDock.objects.create(
            cliente=cliente,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Consultar Cartao',
            codigo_retorno='400',
        )
        card_obj = 'error'
    return card_obj


# Alterar dados do individuo na dock
# Sistema de Log Ja incluso na chamada
def atualizar_individuo_dock(cliente, cliente_cartao):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': gerar_token(client_id, client_password),
    }

    url = f'{url_base}/v2/individuals/{cliente_cartao.id_registro_dock}'
    retorno = {}
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        numero_cpf = ''
        banco = ''
        agencia = ''
        conta = ''

        try:
            cliente_dados_bancarios = DadosBancarios.objects.filter(
                cliente=cliente
            ).first()
            banco = cliente_dados_bancarios.conta_banco or ''
            agencia = cliente_dados_bancarios.conta_agencia or ''
            conta = cliente_dados_bancarios.conta_numero or ''
        except Exception as e:
            logger.error(
                f'Erro ao formatar dados bancários (atualizar_individuo_dock): {e}',
                exc_info=True,
            )

        try:
            numero_cpf = cliente.nu_cpf.replace('.', '').replace('-', '')
        except Exception as e:
            logger.error(
                f'Erro ao formatar cpf (atualizar_individuo_dock): {e}', exc_info=True
            )

        payload = json.dumps({
            'name': cliente.nome_cliente,
            'preferredName': cliente.nome_cliente,
            'motherName': cliente.nome_mae,
            'idNumber': '',
            'document': numero_cpf,
            'birthDate': str(cliente.dt_nascimento),
            'gender': cliente.sexo[:1],
            'identityIssuingEntity': cliente.documento_orgao_emissor,
            'federativeUnit': cliente.endereco_uf,
            'issuingDateIdentity': str(cliente.documento_data_emissao),
            'idProfession': '',
            'idNationality': 1,
            'bankNumber': banco,
            'branchNumber': agencia,
            'accountNumber': conta,
            'email': cliente.email,
            'isPep': cliente.ppe,
            'fatherName': cliente.nome_pai,
        })
        request = requests.request('PUT', url, headers=headers, data=payload)
        response = json.loads(request.text)
        if request.status_code == 202:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'payload[{payload}], response[{response}]',
                nome_chamada='Atualizar dados indivíduo',
                codigo_retorno=request.status_code,
            )
            retorno = 'ok'
        else:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'payload[{payload}], response[{response}]',
                nome_chamada='Atualizar dados indivíduo',
                codigo_retorno=request.status_code,
            )
            enviar_email(
                f'Ocorreu um erro ao tentar atualizar dados do indivíduo na dock, code_status={request.status_code}, payload[{payload}], response[{response}]'
            )
            retorno = 'error'

    except Exception as e:
        print(f'Erro.: {e}')
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            cliente=cliente,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Atualizar dados indivíduo',
            codigo_retorno='400',
        )
        enviar_email(
            f'Ocorreu um erro ao tentar atualizar dados do indivíduo na dock code_status=400, msg={e}'
        )
        retorno = 'error'
        logger.error(
            f'Dock - Erro ao atualizar indivíduo, cliente {cliente.id_unico}',
            exc_info=True,
        )

    return retorno


# Alterar endereço na dock
# Sistema de Log Ja incluso na chamada
def atualizar_endereco_dock(cliente, cliente_cartao):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': gerar_token(client_id, client_password),
    }

    url = f'{url_base}/enderecos'
    retorno = {}
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        endereco_cep = ''
        try:
            endereco_cep = cliente.endereco_cep.replace('-', '')
        except Exception as e:
            logger.error(
                f'Erro ao formatar cep (atualizar_endereco_dock): {e}', exc_info=True
            )

        payload = {
            'bairro': cliente.endereco_bairro,
            'cidade': cliente.endereco_cidade,
            'id': cliente_cartao.id_endereco_dock,
            'idPessoa': cliente_cartao.id_registro_dock,
            'idTipoEndereco': 1,  # 1 = Home address; 2 = Business address; 3 = Mailing address
            'logradouro': cliente.endereco_logradouro,
            'uf': cliente.endereco_uf,
            'cep': endereco_cep,
            'complemento': cliente.endereco_complemento,
            'numero': cliente.endereco_numero,
            'pais': 'Brasil',
            'pontoReferencia': '',
            # "tempoResidenciaAnos":1,
            # "tempoResidenciaMeses":12,
        }

        request = requests.request('PUT', url, headers=headers, data=payload)
        response = json.loads(request.text)

        if request.status_code == 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar endereço Dock',
                codigo_retorno=request.status_code,
            )
            retorno = 'ok'
        else:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar endereço Dock',
                codigo_retorno=request.status_code,
            )

            enviar_email(
                f'Ocorreu um erro ao tentar atualizar endereço na dock, code_status={request.status_code}, payload[{payload}], response[{response}]'
            )
            retorno = 'error'

    except Exception as e:
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            cliente=cliente,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Atualizar endereço Dock',
            codigo_retorno='400',
        )

        logger.error(
            f'Dock - Erro ao atualizar endereço, cliente {cliente.id_unico}',
            exc_info=True,
        )
        enviar_email(
            f'Ocorreu um erro ao tentar atualizar endereço na dock, code_status=400, msg={e}'
        )
        retorno = 'error'

    return retorno


# Alterar endereço de correspondencia na dock
# Sistema de Log Ja incluso na chamada
def atualizar_endereco_correspondencia_dock(cliente, cliente_cartao):
    retorno = {}
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': gerar_token(client_id, client_password),
        }

        url = f'{url_base}/enderecos/{cliente_cartao.id_endereco_dock}/alterar-endereco-correspondencia'

        payload = {'idConta': cliente_cartao.id_conta_dock}

        request = requests.request('PUT', url, headers=headers, data=payload)
        response = json.loads(request.text)

        if request.status_code == 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar endereço correspondencia Dock',
                codigo_retorno=request.status_code,
            )
            retorno = 'ok'
        else:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar endereço correspondencia Dock',
                codigo_retorno=request.status_code,
            )
            retorno = 'error'

    except Exception as e:
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            cliente=cliente,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Atualizar endereço correspondencia Dock',
            codigo_retorno='400',
        )
        logger.error(
            f'Dock - Erro ao atualizar endereço de correspondência, cliente {cliente.id_unico}',
            exc_info=True,
        )
        enviar_email(
            f'Ocorreu um erro ao tentar atualizar endereço de correspondencia na dock, code_status=400, msg={e}'
        )
        retorno = 'error'

    return retorno


# Alterar telefone na dock
# Sistema de Log Ja incluso na chamada
def atualizar_telefone_dock(cliente, cliente_cartao):
    try:
        token = gerar_token(client_id, client_password)
        ddd_cliente = ''
        numero_cliente = ''
        try:
            ddd_cliente = f'0{cliente.telefone_celular[1:3]}'
            numero_cliente = (
                cliente.telefone_celular[4:].replace('-', '').replace(' ', '')
            )
        except Exception as e:
            logger.error(
                f'Erro ao formatar telefones (atualizar_telefone_dock): {e}',
                exc_info=True,
            )

        url = f'{url_base}/telefones'
        retorno = {}
        log_api = LogCliente.objects.get(cliente=cliente)

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': token,
        }

        payload = {
            'id': cliente_cartao.id_telefone_dock,
            'idTipoTelefone': 18,
            'ddd': ddd_cliente,
            'telefone': numero_cliente,
        }

        request = requests.request('PUT', url, headers=headers, data=payload)
        response = json.loads(request.text)

        if request.status_code == 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar telefone Dock',
                codigo_retorno=request.status_code,
            )
            retorno = 'ok'
        else:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}',
                payload_envio=payload,
                nome_chamada='Atualizar telefone Dock',
                codigo_retorno=request.status_code,
            )
            enviar_email(
                f'Ocorreu um erro ao tentar atualizar telefone na dock, code_status={request.status_code}, payload[{payload}], response[{response}]'
            )
            retorno = 'error'

    except Exception as e:
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            cliente=cliente,
            id_cliente=cliente_cartao.id_registro_dock,
            payload=e,
            nome_chamada='Atualizar telefone Dock',
            codigo_retorno='400',
        )

        logger.error(
            f'Dock - Erro ao atualizar telefone, cliente {cliente.id_unico}',
            exc_info=True,
        )
        enviar_email(
            f'Ocorreu um erro ao tentar atualizar telefone na dock, code_status=400, msg={e}'
        )
        retorno = 'error'

    return retorno


@shared_task(bind=True, max_retries=0)  # set max_retries to 0
def ajustes_financeiros(self, contrato_id, contrato_tipo_id, retry_count=0):
    contrato = Contrato.objects.get(pk=contrato_id)
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        contrato_sec = CartaoBeneficio.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_financiado)
        # valor_saque = float(contrato_sec.valor_saque)
        cliente_cartao = contrato.cliente_cartao_contrato.get()

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        contrato_sec = SaqueComplementar.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_lancado_fatura)
        # valor_saque = float(contrato_sec.valor_saque)
        cliente_cartao = contrato_sec.id_cliente_cartao

    cliente = contrato.cliente
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        auth = gerar_token(client_id, client_password)
        url = f'{url_base}/ajustes-financeiros'

        if settings.ORIGIN_CLIENT == 'DIGIMAIS':
            if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                idTipoAjuste = 21036
            else:
                idTipoAjuste = 21038
        else:
            if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                idTipoAjuste = 20092  # 21036
            else:
                idTipoAjuste = 20094  # 21038

        data_atual = datetime.now()
        dataAjuste = data_atual.strftime('%Y-%m-%dT%H:%M:%S')

        payload = {
            'idTipoAjuste': idTipoAjuste,
            'dataAjuste': f'{dataAjuste}',
            'valorAjuste': valor_financiado,
            'flagAtendimento': True,
            'mensagemAtendimento': 'Lançamento do valor de Saque do limite do cartão consignado',
            'idConta': cliente_cartao.id_conta_dock,
        }
        headers = {'Authorization': auth, 'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers)
        ajuste = json.loads(response.text)

        logger.info('ajuste: %s', ajuste)

        if response.status_code != 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=ajuste,
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros',
                codigo_retorno=response.status_code,
            )

            logger.error(
                f'Dock - Erro no lançamento do saque, cliente {cliente.nome_cliente}',
                exc_info=True,
            )
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}.\nVamos tentar novamente',
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros',
                codigo_retorno=response.status_code,
            )
            raise Exception('Dock retornou erro no lançamento do saque.')
        else:
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                alterar_status(
                    contrato,
                    contrato_sec,
                    EnumContratoStatus.PAGO,
                    ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                )

                contrato.dt_pagamento_contrato = datetime.now()
                contrato.save()

            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=ajuste,
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros',
                codigo_retorno=response.status_code,
            )
    except Exception as e:
        logger.error(
            f'Dock - A tentativa de lançamento do saque falhou, contrato: {contrato}, cliente {cliente.nome_cliente}: {e}',
            exc_info=True,
        )
        if retry_count < 2:  # Se o número de tentativas for menor que 2
            try:
                ajustes_financeiros.apply_async(
                    args=[contrato_id, contrato_tipo_id, retry_count + 1],
                    countdown=30 * 60,
                )  # reagende a tarefa
            except Exception as ex:
                print(ex)
                RetornosDock.objects.create(
                    log_api_id=log_api.id,
                    id_cliente=cliente_cartao.id_registro_dock,
                    payload=ex,
                    nome_chamada='Ajustes financeiros',
                    codigo_retorno='400',
                )
                enviar_email(
                    f'Alerta: A tentativa de lançamento do saque do cliente {cliente.nome_cliente} para o '
                    f'contrato número {contrato} falhou.'
                )


@shared_task(bind=True, max_retries=0)  # set max_retries to 0
def ajustes_financeiros_estorno(self, contrato_id, contrato_tipo_id, retry_count=0):
    contrato = Contrato.objects.get(pk=contrato_id)
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        contrato_sec = CartaoBeneficio.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_financiado)
        # valor_saque = float(contrato_sec.valor_saque)
        cliente_cartao = contrato.cliente_cartao_contrato.get()

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        contrato_sec = SaqueComplementar.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_lancado_fatura)
        # valor_saque = float(contrato_sec.valor_saque)
        cliente_cartao = contrato_sec.id_cliente_cartao

    cliente = contrato.cliente

    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        auth = gerar_token(client_id, client_password)
        url = f'{url_base}/ajustes-financeiros'

        idTipoAjuste = 20093
        data_atual = datetime.now()
        dataAjuste = data_atual.strftime('%Y-%m-%dT%H:%M:%S')

        payload = {
            'idTipoAjuste': idTipoAjuste,
            'dataAjuste': f'{dataAjuste}',
            'valorAjuste': valor_financiado,
            'flagAtendimento': True,
            'mensagemAtendimento': 'Estorno do valor de Saque do limite do cartão consignado',
            'idConta': cliente_cartao.id_conta_dock,
        }
        headers = {'Authorization': auth, 'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers)
        ajuste = json.loads(response.text)

        print('Estorno', ajuste)
        logger.info('ajuste: %s', ajuste)

        if response.status_code != 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=ajuste,
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros',
                codigo_retorno=response.status_code,
            )

            logger.error(
                f'Dock - Erro no lançamento do estorno do saque, cliente {cliente.nome_cliente}',
                exc_info=True,
            )
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response}.\nVamos tentar novamente',
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros - Estorno',
                codigo_retorno=response.status_code,
            )
            raise Exception('Dock retornou erro no lançamento do estorono do saque.')
        else:
            contrato_sec.status = ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value
            contrato_sec.save()
            contrato.dt_pagamento_contrato = datetime.now()
            contrato.save()
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
            )
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=ajuste,
                payload_envio=payload,
                nome_chamada='Ajustes Financeiros',
                codigo_retorno=response.status_code,
            )
    except Exception as e:
        logger.error(
            msg=f'Dock - A tentativa de lançamento do estorno do saque falhou, contrato: {contrato}, cliente {cliente.nome_cliente}: {e}'
        )
        logger.error(
            f'Dock - A tentativa de lançamento do estorno do saque falhou, contrato: {contrato}, cliente {cliente.nome_cliente}',
            exc_info=True,
        )
        if retry_count < 2:  # Se o número de tentativas for menor que 2
            try:
                ajustes_financeiros_estorno.apply_async(
                    args=[contrato_id, contrato_tipo_id, retry_count + 1],
                    countdown=30 * 60,
                )  # reagende a tarefa
            except Exception as ex:
                print(ex)
                RetornosDock.objects.create(
                    log_api_id=log_api.id,
                    id_cliente=cliente_cartao.id_registro_dock,
                    payload=ex,
                    nome_chamada='Ajustes financeiros - Estorno',
                    codigo_retorno='400',
                )
                enviar_email(
                    f'Alerta: A tentativa de lançamento do estorno do saque do cliente {cliente.nome_cliente} para o '
                    f'contrato número {contrato} falhou.'
                )


@shared_task(bind=True, max_retries=0)  # set max_retries to 0
def lancamento_saque_parcelado_fatura(
    self, contrato_id, contrato_tipo_id, retry_count=0
):
    auth = gerar_token(client_id, client_password)

    contrato = Contrato.objects.get(pk=contrato_id)
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        contrato_sec = CartaoBeneficio.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_financiado)
        valor_total_a_pagar = float(contrato_sec.valor_total_a_pagar)
        source = 'SAP'

        cliente_cartao = contrato.cliente_cartao_contrato.get()

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        contrato_sec = SaqueComplementar.objects.get(pk=contrato_tipo_id)
        valor_financiado = float(contrato_sec.valor_lancado_fatura)
        valor_total_a_pagar = float(contrato_sec.valor_total_a_pagar)
        source = 'SCP'

        cliente_cartao = contrato_sec.id_cliente_cartao

    cliente = contrato.cliente
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        url = f'{url_base}/purchases'
        retorno_saque = RetornoSaque.objects.filter(contrato=contrato).first()
        if retorno_saque.Status == 'rep':
            # Encerra a execução da função para evitar loop infinito
            return
        convenio = Convenios.objects.filter(pk=cliente_cartao.convenio.pk).first()
        produto_convenio = ProdutoConvenio.objects.filter(
            convenio=convenio, produto=contrato.tipo_produto
        ).first()
        purchase_value = round(float(valor_total_a_pagar) - float(valor_financiado), 2)

        data_formatada = retorno_saque.DtCriacao.strftime('%Y-%m-%d %H:%M:%S.000')

        # Converta a string formatada de volta para um objeto datetime
        data_objeto = datetime.strptime(data_formatada, '%Y-%m-%d %H:%M:%S.%f')

        # Agora, ajustamos a hora para meia-noite
        data_objeto = data_objeto.replace(hour=0, minute=0, second=0, microsecond=0)

        # Finalmente, formatamos o objeto datetime para a string desejada
        data_final = data_objeto.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        establishment_id = 9  # MODIFICAR DEPOIS

        if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            data_formatada = contrato.ultima_atualizacao.strftime(
                '%Y-%m-%d %H:%M:%S.000'
            )
            # Converta a string formatada de volta para um objeto datetime
            data_objeto = datetime.strptime(data_formatada, '%Y-%m-%d %H:%M:%S.%f')
            # Agora, ajustamos a hora para meia-noite
            data_objeto = data_objeto.replace(hour=0, minute=0, second=0, microsecond=0)
            # Finalmente, formatamos o objeto datetime para a string desejada
            data_final = data_objeto.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        payload = {
            'establishment_id': establishment_id,
            'account_id': int(cliente_cartao.id_conta_dock),
            'card_id': int(cliente_cartao.id_cartao_dock),
            'purchase_date': data_final,
            'operation_id': produto_convenio.saque_parc_cod_dock,
            'plots_number': contrato_sec.qtd_parcela_saque_parcelado,
            'plots_value': f'{contrato_sec.valor_parcela}',
            'contract_value': f'{valor_total_a_pagar}',
            'purchase_value': f'{valor_financiado}',
            'total_charges_value': float(purchase_value),
            'interest_rate_value': float(produto_convenio.taxa_produto),
            'IOF_value': f'{float(contrato.vr_iof_total)}',
            'TAC_value': '0.0000',
            'source': source,
            'lack': 0,
            'establishment_name': 'AMIGOZ',
            'first_installment_value': f'{contrato_sec.valor_parcela}',
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': auth,
        }

        response = requests.post(url, json=payload, headers=headers)
        response_text = json.loads(response.text)

        if response.status_code != 200:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=response_text,
                payload_envio=payload,
                nome_chamada='Lançamento saque parcelado',
                codigo_retorno=response.status_code,
            )

            logger.error(
                f'Dock - Erro no lançamento do saque parcelado, cliente {cliente.nome_cliente}',
                exc_info=True,
            )
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=f'{response_text}.\nVamos tentar novamente',
                payload_envio=payload,
                nome_chamada=f'Lançamento saque parcelado - Tentativa {retry_count + 1}',
                codigo_retorno=response.status_code,
            )
            raise Exception('Dock retornou erro no lançamento do saque parcelado.')
        else:
            contrato.dt_pagamento_contrato = datetime.now()
            contrato.save()

            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                alterar_status(
                    contrato,
                    contrato_sec,
                    EnumContratoStatus.PAGO,
                    ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                )

            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente_cartao.id_registro_dock,
                payload=response_text,
                payload_envio=payload,
                nome_chamada='Lançamento saque parcelado',
                codigo_retorno=response.status_code,
            )
    except Exception as e:
        logger.error(
            f'Dock - A tentativa de lançamento do saque parcelado falhou, contrato: {contrato}, cliente {cliente.nome_cliente}: {e}',
            exc_info=True,
        )
        if retry_count < 4:  # Se o número de tentativas for menor que 4
            try:
                lancamento_saque_parcelado_fatura.apply_async(
                    args=[contrato_id, contrato_tipo_id, retry_count + 1],
                    countdown=30 * 60,
                )  # reagende a tarefa
            except Exception as ex:
                print(ex)
                RetornosDock.objects.create(
                    log_api_id=log_api.id,
                    id_cliente=cliente_cartao.id_registro_dock,
                    payload=ex,
                    nome_chamada='Lançamento saque parcelado',
                    codigo_retorno='400',
                )
                enviar_email(
                    f'Alerta: A tentativa de lançamento do saque parcelado do cliente {cliente.nome_cliente} para o '
                    f'contrato número {contrato} falhou.'
                )
