import json

import requests
from django.conf import settings

from handlers.auth_hub_inss import autenticacao_hub_inss


def opcoes_contrato_inss(
    dt_nascimento,
    tipo_contrato,
    codigo_beneficio,
    margem_livre,
    valor_parcela,
    valor_contrato,
    first_due_date,
):
    # data_atual = date.today()
    if valor_contrato <= 0 and valor_parcela <= 0:
        valor_contrato = 0
        valor_parcela = 0

    # idade_maxima_simulacao = 80
    # comissao_taxa = 1.8


def consulta_beneficios_hub(numero_cpf):
    authorization = autenticacao_hub_inss()
    url = f'{settings.HUB_API_URL}/Bureau/ObterINSSDadosPorCpf?Cpf={str(numero_cpf)}'

    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }

    response = requests.request('GET', url, headers=headers, data='')
    consulta_Beneficios_obj = json.loads(response.text)

    return [
        {
            'numero_beneficio': beneficio['nuBeneficio'],
            'valor_receita': beneficio['vrReceita'],
            'numero_tipo_beneficio': beneficio['nuTipoBeneficio'],
            'nome_beneficio': beneficio['txDescricao'],
        }
        for beneficio in consulta_Beneficios_obj['beneficios']
        if beneficio['adicionais']['flAtivo']
    ]
