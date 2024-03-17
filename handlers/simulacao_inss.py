import json
from datetime import datetime

import requests
from django.conf import settings

from api_log.models import LogWebhook
from contract.products.consignado_inss.utils import converter_parametros
from handlers.auth_hub_inss import autenticacao_hub_inss


def simulacao_hub_inss(
    numero_cpf,
    dt_nascimento,
    codigo_beneficio,
    numero_beneficio,
    margem_livre,
    valor_parcela,
):
    # Função para aplicar os padrões de regex e converter camelCase para snake_case

    token_hub = autenticacao_hub_inss()
    url = f'{settings.DNG_API_URL}/Digitacao/SimularContratoMargemLivre'

    numero_cpf = numero_cpf.replace('.', '').replace('-', '')
    numero_cpf = int(numero_cpf)
    data_obj = datetime.strptime(dt_nascimento, '%d/%m/%Y')
    dt_nascimento = data_obj.strftime('%Y-%m-%d')

    payload = json.dumps({
        'cpf': numero_cpf,
        'dtNascimento': dt_nascimento,
        'cdInssBeneficioTipo': codigo_beneficio,
        'nuBeneficio': numero_beneficio,
        'vrMargemLivre': f'{margem_livre}',
        'vrParcela': valor_parcela,
    })

    headers = {
        'Authorization': f'Bearer {token_hub}',
        'Content-Type': 'application/json',
    }
    # regex_patterns = {
    #     'upper': re.compile(r'([A-Z]+)'),
    #     'special': re.compile(r'[^a-zA-Z0-9]+'),
    #     'start': re.compile(r'^_+'),
    # }

    response = requests.request('POST', url, headers=headers, data=payload)
    resposta = {}
    if response.status_code in {200, 201, 202}:
        response_obj = json.loads(response.text)
        simulacao_obj = converter_parametros(response_obj)
        resposta['retornado'] = True
        resposta['simulacao_obj'] = simulacao_obj
    else:
        response_txt = response.text
        resposta['retornado'] = False
        # A data e a hora atuais
        agora = datetime.now()
        # Formatar a data e a hora
        formatado = agora.strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'ERRO SIMULAÇÃO-INSS {formatado}',
            log_webhook=response_txt,
        )
    return resposta
