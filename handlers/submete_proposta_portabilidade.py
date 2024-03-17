import json
import logging
import typing

import requests
from django.conf import settings

from api_log.constants import EnumStatusCCB
from api_log.models import LogCliente, QitechRetornos
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from custom_auth.models import UserProfile
from handlers.insere_proposta_inss_financeira import autenticacao_hub
from utils.hub import get_hub_financeira_response, get_product_qitech_endpoint

logger = logging.getLogger('digitacao')

HTTP_VERBS = typing.Literal[
    'GET',
    'POST',
    'PATCH',
    'PUT',
    'DELETE',
]


def submete_proposta_portabilidade_financeira_hub(contrato, status):
    """Realiza a submissão de uma nova proposta na financeira Qi Tech e inclui a CCB retornada por eles nos anexos do
    contrato no nosso banco de dados"""
    from contract.constants import QI_TECH_ENDPOINTS
    from contract.api.views.get_qi_tech_data import execute_qi_tech_get

    try:
        CONST_HUB_FINANCEIRA_QITECH_URL = (
            f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
        )

        authorization = autenticacao_hub()

        headers = {
            'Authorization': f'Bearer {authorization}',
            'Content-Type': 'application/json',
        }

        portabilidade = Portabilidade.objects.get(contrato=contrato)
        proposal_key = portabilidade.chave_proposta
        payload = {
            'NmEndpoint': f'v2/credit_transfer/proposal/{proposal_key}',
            'NmVerb': 'PATCH',
            'JsonBody': {'status': str(status)},
        }
        response = requests.request(
            'POST',
            CONST_HUB_FINANCEIRA_QITECH_URL,
            headers=headers,
            data=json.dumps(payload),
        )
        insere_proposta_inss_financeira_obj_response = json.loads(response.text)
        json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)
        endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + portabilidade.chave_proposta
        consulta = execute_qi_tech_get(endpoint).data
        if response.status_code in {200, 201, 202} or (
            'proposal_status' in consulta
            and consulta['proposal_status']
            in ('pending_response', 'pending_acceptance')
        ):
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=contrato.cliente,
                retorno=insere_proposta_inss_financeira_obj_response,
                tipo=status,
            )
            portabilidade.sucesso_submissao_proposta = True
            portabilidade.save()
            if status == 'pending_response':
                portabilidade.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
                portabilidade.save()
            if response.status_code in {200, 201, 202}:
                message = (
                    f'{contrato.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                    f'  Proposta submetida com sucesso.'
                )
            else:
                message = (
                    f'{contrato.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                    f'  Proposta já havia sido submetida com sucesso.'
                )
            logger.info(message)
            return True
        else:
            portabilidade.sucesso_submissao_proposta = False
            portabilidade.motivo_submissao_proposta = (
                f'Status: {response.status_code}\n'
                f" Descrição:{json_obj_response['translation']}\n"
                f"CODIGO ERRO(QITECH) :{json_obj_response['code']}"
            )
            portabilidade.save()
            message = (
                f'{contrato.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
                f'  Erro na submissão da proposta.'
            )
            logger.error(
                message, extra={'extra': insere_proposta_inss_financeira_obj_response}
            )
            return False
    except Exception as e:
        json_formated = str(e)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=json_formated,
            tipo='Received Signature',
        )
        message = (
            f'{contrato.cliente.id_unico} - Contrato(ID: {contrato.pk}):'
            f' Erro na submissão da proposta (Exception).'
        )
        logger.error(message, extra={'extra': json_formated})
        return False


def aceita_proposta_portabilidade_financeira_hub(contrato, status):
    """Realiza a submissão de uma nova proposta na financeira Qi Tech e inclui a CCB retornada por eles nos anexos do
    contrato no nosso banco de dados"""

    CONST_HUB_FINANCEIRA_QITECH_URL = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )

    authorization = autenticacao_hub()

    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }

    portabilidade = Portabilidade.objects.get(contrato=contrato)
    proposal_key = portabilidade.chave_proposta
    payload = {
        'NmEndpoint': f'v2/credit_transfer/proposal/{proposal_key}',
        'NmVerb': 'PATCH',
        'JsonBody': {
            'status': str(status),
            'financial': {
                'installment_face_value': float(portabilidade.valor_parcela_recalculada)
            },
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
    if response.status_code in {200, 201, 202}:
        # Inicio: Fluxo de sucesso
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=insere_proposta_inss_financeira_obj_response,
            tipo=status,
        )
        portabilidade.sucesso_aceite_proposta = True
        portabilidade.save(update_fields=['sucesso_aceite_proposta'])
        if status == 'pending_response':
            portabilidade.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
            portabilidade.save(update_fields=['status_ccb'])

        logger.info(
            f'{contrato.cliente.id_unico} - Contrato({contrato.pk}): Proposta de portabilidade aceita.\n Payload {payload}'
        )
        return json_obj_response
        # Fim: Fluxo de sucesso
    else:
        # Inicio: Fluxo de erro
        user = UserProfile.objects.get(identifier='30620610000159')
        user = UserProfile.objects.get(identifier=user.identifier)
        # if json_obj_response['code'] == 'CT000021':
        #     portabilidade.status = ContractStatus.REPROVADO.value
        #     portabilidade.save(update_fields=['status'])
        #
        #     StatusContrato.objects.create(
        #         contrato=contrato, nome=ContractStatus.REPROVADO.value, created_by=user
        #     )
        #     recusa_proposta_portabilidade_financeira_hub(contrato, 'DELETE')
        #     portabilidade.sucesso_aceite_proposta = False
        #     portabilidade.motivo_aceite_proposta = (
        #         f'Status: {response.status_code}\n'
        #         f" Descrição:{json_obj_response['translation']}\n"
        #         f"CODIGO ERRO(QITECH) :{json_obj_response['code']}"
        #     )
        #     portabilidade.save(
        #         update_fields=['sucesso_aceite_proposta', 'motivo_aceite_proposta']
        #     )
        #
        #     return False

        if json_obj_response['code'] == 'SSC000041':
            portabilidade.status = ContractStatus.REPROVADO.value
            portabilidade.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=contrato, nome=ContractStatus.REPROVADO.value, created_by=user
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()
        portabilidade.motivo_aceite_proposta = (
            f'Status: {response.status_code}\n'
            f" Descrição:{json_obj_response['translation']}\n"
            f"CODIGO ERRO(QITECH) :{json_obj_response['code']}"
        )
        portabilidade.sucesso_aceite_proposta = False
        portabilidade.save()
        return False


def recusa_proposta_portabilidade_financeira_hub(contrato, status):
    """Realiza a recusa da proposta de portabilidade na QITECH"""

    CONST_HUB_FINANCEIRA_QITECH_URL = (
        f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute'
    )

    authorization = autenticacao_hub()

    headers = {
        'Authorization': f'Bearer {authorization}',
        'Content-Type': 'application/json',
    }
    portabilidade = Portabilidade.objects.get(contrato=contrato)
    proposal_key = portabilidade.chave_proposta
    payload = {
        'NmEndpoint': f'v2/credit_transfer/proposal/{proposal_key}',
        'NmVerb': 'delete',
    }
    response = requests.request(
        'POST',
        CONST_HUB_FINANCEIRA_QITECH_URL,
        headers=headers,
        data=json.dumps(payload),
    )
    insere_proposta_inss_financeira_obj_response = json.loads(response.text)
    json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)
    if response.status_code in {200, 201, 202}:
        portabilidade.sucesso_recusa_proposta = True

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=insere_proposta_inss_financeira_obj_response,
            tipo=status,
        )
        portabilidade.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
        portabilidade.save()
        logger.info(
            f'{contrato.cliente.id_unico} - Contrato({contrato.pk}):Recusa enviada para QITECH.\n Payload {payload}'
        )
        return True
    else:
        if (
            json_obj_response['code'] != 'CT000010'
        ):  # Codigo de erro de quando a proposta ja foi cancelada
            portabilidade.sucesso_recusa_proposta = False
            portabilidade.motivo_recusa_proposta = (
                f'Status: {response.status_code}\n'
                f" Descrição:{json_obj_response['translation']} {json_obj_response['code']}"
            )
            portabilidade.save()
            return False
        else:
            portabilidade.sucesso_recusa_proposta = True
            portabilidade.save()
            logger.info(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}):Proposta ja havia sido cancelada na QITECH.\n Payload {payload}'
            )
            return True


def refuse_product_proposal_qitech(
    contract: Contrato,
    product: typing.Union[Refinanciamento, Portabilidade],
    http_verb: HTTP_VERBS = 'DELETE',
):
    """
    Refuses proposal from specific product.

    Args:
        contract: Contract
        product: Product to be cancelled
        http_verb: Http Verb that will be sent to HUB.
    """
    payload = {
        'NmEndpoint': get_product_qitech_endpoint(product),
        'NmVerb': http_verb,
    }

    response = get_hub_financeira_response(payload)
    status_code = response.status_code
    insere_proposta_inss_financeira_obj_response = json.loads(response.text)
    json_obj_response = json.loads(insere_proposta_inss_financeira_obj_response)

    if status_code in (200, 201, 202):
        product.sucesso_recusa_proposta = True

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contract.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contract.cliente,
            retorno=insere_proposta_inss_financeira_obj_response,
            tipo=http_verb,
        )
        product.status_ccb = EnumStatusCCB.PENDING_RESPONSE.value
        product.save()
        logger.info(
            f'{contract.cliente.id_unico} - Contrato({contract.pk}):Recusa enviada para QITECH.\n Payload {payload}'
        )
        return True
    else:
        if (
            json_obj_response['code'] != 'CT000010'
        ):  # Codigo de erro de quando a proposta ja foi cancelada
            product.sucesso_recusa_proposta = False
            product.motivo_recusa_proposta = (
                f'Status: {status_code}\n'
                f" Descrição:{json_obj_response['translation']} {json_obj_response['code']}"
            )
            product.save()
            return False
        else:
            product.sucesso_recusa_proposta = True
            product.save()
            logger.info(
                f'{contract.cliente.id_unico} - Contrato({contract.pk}):Proposta ja havia sido cancelada na QITECH.\n Payload {payload}'
            )
            return True
