import json
import logging

import requests
from django.conf import settings

from contract.models.contratos import Contrato, Portabilidade
from handlers.insere_proposta_inss_financeira import autenticacao_hub

logger = logging.getLogger('digitacao')


def modifica_proposta_portabilidade_financeira_hub(token, value):
    """Realiza a modificação de uma nova proposta na financeira Qi Tech e inclui a CCB retornada por eles nos anexos
    do contrato no nosso banco de dados"""

    CONST_HUB_FINANCEIRA_QITECH_URL = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )

    authorization = autenticacao_hub()

    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }
    contratos = Contrato.objects.filter(token_envelope=token)

    for contrato in contratos:
        portabilidade = Portabilidade.objects.get(contrato=contrato)
        proposal_key = portabilidade.chave_proposta
        payload = {
            'NmEndpoint': f'v2/credit_transfer/proposal/{proposal_key}',
            'NmVerb': 'PATCH',
            'JsonBody': {
                'status': 'accepted_by_requester',
                'financial': {'montlhy_interest_rate': value},
            },
        }
        response = requests.request(
            'POST',
            CONST_HUB_FINANCEIRA_QITECH_URL,
            headers=headers,
            data=json.dumps(payload),
        )
        insere_proposta_inss_financeira_obj_response = json.loads(response.text)
        json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)
        logger.info(
            f'{contrato.cliente.id_unico} - Contrato({contrato.pk}): Proposta alterada na QITECH.\n Payload {payload}'
        )
        return json_obj_response['JsonResponse']['translation']
