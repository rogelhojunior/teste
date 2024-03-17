import json
import logging

import requests
from django.conf import settings

from api_log.models import LogCliente, TemSaudeAdesao
from contract.constants import EnumStatus
from core.models import BeneficiosContratado

logger = logging.getLogger('digitacao')


# Função Para gerar token Zeus na API da tem saude
def gerar_token_zeus():
    payload = {
        'companyId': str(settings.TEMSAUDE_COMPANYID),
        'apiKey': settings.TEMSAUDE_APIKEY,
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = requests.request(
        'POST', settings.URL_TOKEN_ZEUS, headers=headers, data=payload
    )

    response_dict = json.loads(response.text)
    return response_dict['data']['token']


# Função para adicionar um novo cliente (nova vida) no sistema da tem saude
def adesao(cliente, token_zeus, contrato, plano):
    url = f'{settings.URL_TEMSAUDE}/tem_adesao'
    cpf_cliente = cliente.nu_cpf.replace('.', '').replace('-', '')
    cod_onix = plano.codigo_plano
    logger.info('Envio das informações de seguro TEM SAUDE')
    payload = {
        'cpfTitular': '',
        'CodOnix': cod_onix,
        'Nome': f'{cliente.nome_cliente}',
        'cpf': f'{cpf_cliente}',
        'data_nascimento': f'{cliente.dt_nascimento}',
        'Sexo': '',
        'email': f'{cliente.email}',
        'NumeroCartao': '',
        'cnpj': settings.CONST_CNPJ_AMIGOZ,
        'Logradouro': f'{cliente.endereco_logradouro}',
        'NumeroEndereco': f'{cliente.endereco_numero}',
        'Complemento': '',
        'Bairro': f'{cliente.endereco_bairro}',
        'Cidade': f'{cliente.endereco_cidade}',
        'Estado': f'{cliente.endereco_uf}',
        'CEP': f'{cliente.endereco_cep}',
        'Telefone': f'{cliente.telefone_celular}',
        'numerodasorte': '',
        'tokenzeus': f'{token_zeus}',
        'cn': '',
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.request('POST', url, headers=headers, json=payload)
    logger.info(f'Resposta TEM SAUDE: {response.json()}')
    response_dict = json.loads(response.text)
    log_api = LogCliente.objects.get(cliente=cliente)
    try:
        if response_dict['UserToken']:
            cliente_cartao = contrato.cliente_cartao_contrato.get()
            cliente_cartao.token_usuario_tem_saude = response_dict['UserToken']
            cliente_cartao.cartao_tem_saude = response_dict['NumeroCartao']
            cliente_cartao.save()

        TemSaudeAdesao.objects.create(
            log_api=log_api,
            nome=cliente.nome_cliente,
            tipo_servico='Adesão',
            payload=response_dict['message'],
        )

    except Exception as e:
        logger.error(f'Erro ao criar TemSaudeAdesao (adesao): {e}')
        TemSaudeAdesao.objects.create(
            log_api=log_api,
            nome=cliente.nome_cliente,
            tipo_servico='Adesão',
            payload=response_dict,
        )
    try:
        cliente_cartao = contrato.cliente_cartao_contrato.get()
        identificacao_segurado = cliente_cartao.cartao_tem_saude

        valor_plano = plano.valor_segurado
        premio_bruto = plano.valor_segurado
        renovacao_automatica = plano.renovacao_automatica
        obrigatorio = plano.obrigatorio

        if response.status_code in {200, 202, 201}:
            status = EnumStatus.CRIADO_COM_SUCESSO
        else:
            status = EnumStatus.RECUSADO_ERRO_NECESSITA_DE_ATENCAO

        BeneficiosContratado.objects.create(
            id_conta_dock=cliente_cartao.id_conta_dock or '',
            id_cartao_dock=cliente_cartao.id_registro_dock or '',
            contrato_emprestimo=contrato,
            plano=plano,
            nome_operadora=plano.seguradora.get_nome_display(),
            nome_plano=plano.nome,
            obrigatorio=obrigatorio,
            identificacao_segurado=identificacao_segurado,
            valor_plano=valor_plano,
            premio_bruto=premio_bruto,
            renovacao_automatica=renovacao_automatica,
            cliente=cliente,
            status=status,
            tipo_plano=plano.get_tipo_plano_display(),
        )
    except Exception as e:
        logger.error(f'Erro ao criar objeto Beneficio Contratado: {e}')


# Função Para cancelar o plano tem saude do cliente
def cancelamento_cartao(cliente, token_zeus):
    url = f'{settings.URL_TEMSAUDE}/tem_alteracao_status_cto'
    cpf_cliente = cliente.nu_cpf.replace('.', '').replace('-', '')
    cancelado = 3
    payload = {
        'cpf': cpf_cliente,
        'CodOnix': str(settings.TEMSAUDE_CODONIX),
        'NumeroCartao': '',
        'NovoStatus': cancelado,
        'tokenzeus': token_zeus,
        'UserToken': '',
    }
    headers = {'Content-Type': 'application/json'}

    response = requests.request('POST', url, headers=headers, json=payload)
    response_dict = json.loads(response.text)
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        TemSaudeAdesao.objects.create(
            log_api=log_api,
            nome=cliente.nome_cliente,
            tipo_servico='Cancelamento',
            payload=response_dict['message'],
        )
    except Exception as e:
        logger.error(f'Erro ao criar TemSaudeAdesao (cancelamento_cartao): {e}')
        TemSaudeAdesao.objects.create(
            log_api=log_api,
            nome=cliente.nome_cliente,
            tipo_servico='Cancelamento',
            payload=response_dict,
        )
