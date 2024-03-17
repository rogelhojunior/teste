import logging
from datetime import datetime

from api_log.models import LogWebhook
from contract.constants import EnumTipoProduto
from handlers.qitech import QiTech
from simulacao.communication.hub import definir_data_primeiro_vencimento


def build_first_due_data(tipo_produto) -> str:
    first_due_data = definir_data_primeiro_vencimento(tipo_produto)
    first_due_data = first_due_data.strftime('%Y-%m-%d')

    return str(first_due_data)


def simulacao_portabilidade_financeira_hub(
    taxa_de_juros_mensal, numero_de_parcelas, ultimo_devido_saldo
):
    logger = logging.getLogger('webhookqitech')
    """function used to simulate portability proposals"""
    qi_tech = QiTech()
    fist_due_date = str(build_first_due_data(EnumTipoProduto.PORTABILIDADE))
    response = qi_tech.simulation_port_v2_fixed_rate(
        numero_de_parcelas, taxa_de_juros_mensal, ultimo_devido_saldo, fist_due_date
    )
    decoded_response = qi_tech.decode_body(response_json=response.json())

    resposta = {}
    if response.status_code in (200, 201, 202):
        resposta['retornado'] = True
        resposta['total_amount'] = decoded_response['portability_credit_operation'][
            'disbursement_options'
        ][0]['installments'][0]['total_amount']
        resposta['annual_cet'] = decoded_response['portability_credit_operation'][
            'disbursement_options'
        ][0]['annual_cet']
    else:
        response_txt = response.text
        resposta['retornado'] = False
        # A data e a hora atuais
        agora = datetime.now()
        # Formatar a data e a hora
        formatado = agora.strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'WEBHOOK QITECH ERRO - SIMULACAO {formatado}',
            log_webhook=response_txt,
        )
        logger.error(f'Houve um ao simular {response_txt}')
    return resposta
