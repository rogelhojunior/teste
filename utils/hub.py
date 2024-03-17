import json
import typing

import requests

from contract.models.contratos import Portabilidade, Refinanciamento
from core import settings
from handlers.insere_proposta_inss_financeira import autenticacao_hub


def get_hub_headers():
    authorization = autenticacao_hub()
    return {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }


def get_hub_financeira_payload(
    endpoint: str,
    http_verb: str,
    **kwargs,
):
    return {
        'NmEndpoint': endpoint,
        'NmVerb': http_verb,
        **kwargs,
    }


def get_hub_financeira_response(payload):
    return requests.request(
        'POST',
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute',
        headers=get_hub_headers(),
        data=json.dumps(payload),
    )


def get_product_qitech_endpoint(
    product: typing.Union[
        Refinanciamento,
        Portabilidade,
    ],
):
    """
    Args:
        product: Product to get endpoint

    Returns:
        Endpoint from QITech

    Raises:
        NotImplemented for other products
    """
    proposal_key = product.chave_proposta

    if isinstance(product, Portabilidade):
        endpoint = f'v2/credit_transfer/proposal/{proposal_key}'
    elif isinstance(product, Refinanciamento):
        endpoint = (
            f'v2/credit_transfer/proposal/{proposal_key}/refinancing_credit_operation'
        )
    else:
        raise NotImplementedError
    return endpoint
