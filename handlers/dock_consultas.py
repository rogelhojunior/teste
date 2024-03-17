import calendar
import json
import logging
from datetime import datetime, timedelta

import requests
from django.conf import settings

from api_log.models import LogCliente, RetornosDock
from handlers.dock_formalizacao import gerar_token
from handlers.email import enviar_email

logger = logging.getLogger('digitacao')

# Credenciais não podem estar no mesmo banco de dados da aplicação -> exigência dock
url_token = settings.DOCK_URL_TOKEN
url_base = settings.DOCK_URL_BASE
client_id = settings.DOCK_CLIENT_ID
client_password = settings.DOCK_CLIENT_PASSWORD


def limites_disponibilidades(id_cartao, cliente, cliente_cartao):
    log_api = LogCliente.objects.get(cliente=cliente)
    url = f'{url_base}/cartoes/{id_cartao}/limites-disponibilidades'
    print(url)
    try:
        auth = gerar_token(client_id, client_password)

        headers = {'Accept': 'application/json', 'Authorization': auth}

        response = requests.get(url, headers=headers)

        response_text = json.loads(response.text)
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            id_cliente=cliente_cartao,
            payload_envio=url,
            payload=f'response[{response_text}]',
            nome_chamada='Consulta Limite Saque',
            codigo_retorno=response.status_code,
        )

        logger.info(
            f'Consulta limite de saque do cartão {id_cartao} do cliente {cliente.nome_cliente}'
        )

        logger.info(f'Response: {response_text}')
        return response_text

    except Exception as e:
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            id_cliente=cliente_cartao,
            payload_envio=url,
            payload=e,
            nome_chamada='Consulta Limite Saque',
            codigo_retorno='400',
        )

        logger.error(
            f'Erro ao consultar limite de saque do cartão {id_cartao} do cliente {cliente.nome_cliente}',
            exc_info=True,
        )
        enviar_email('Alerta: A tentativa de consultar limite da Dock falhou.')


def simulacao_saque_parcelado_dock(
    quantidade_parcelas, valor_saque, produto_convenio, cliente, parametros_backoffice
):
    log_api = LogCliente.objects.get(cliente=cliente)

    try:
        auth = gerar_token(client_id, client_password)

        url = f'{url_base}/transactions/financing/simulations'
        corte = produto_convenio.corte
        vencimento_fatura = produto_convenio.data_vencimento_fatura
        criacao_do_contrato = datetime.now().date()
        data_vencimento = criacao_do_contrato.replace(day=1)
        logger.info({
            'corte': f'- Simulacao saque parcelado dock {corte}',
            'venciment_fatura': f'- Simulacao saque parcelado dock {vencimento_fatura}',
            'ciracao_do_contrato': f'{criacao_do_contrato}',
            'data_vencimento': f'{data_vencimento}',
        })
        if criacao_do_contrato.day > vencimento_fatura:
            data_vencimento = criacao_do_contrato.replace(day=1) + timedelta(days=31)

        dia_simulacao = datetime.now().day

        try:
            if vencimento_fatura < corte:
                if (dia_simulacao > corte and dia_simulacao > vencimento_fatura) or (
                    dia_simulacao < corte and dia_simulacao <= vencimento_fatura
                ):
                    data_vencimento = data_vencimento.replace(day=1) + timedelta(
                        days=31
                    )
            elif dia_simulacao >= corte and dia_simulacao <= vencimento_fatura:
                data_vencimento = data_vencimento.replace(day=1) + timedelta(days=31)

            ultimo_dia_mes = calendar.monthrange(
                data_vencimento.year, data_vencimento.month
            )[1]
            if vencimento_fatura <= ultimo_dia_mes:
                data_vencimento = data_vencimento.replace(day=vencimento_fatura)
            else:
                proximo_mes = data_vencimento.replace(day=1) + timedelta(days=31)
                dias_excedentes = vencimento_fatura - ultimo_dia_mes
                data_vencimento = proximo_mes.replace(day=dias_excedentes)

            logger.info({
                'data_vencimento': f'{data_vencimento} apos validacao regras backoffice'
            })

        except Exception as e:
            logger.error(
                f'Erro ao simular saque. Verificar parametrização (calcula_simulacao_iof): {e}'
            )
            return {'Erro': 'Erro ao simular saque. Verificar parametrização'}

        payload = {
            'business_month': True,
            'iof_removed': False,
            'legal_entity': True,
            'simple_legal_entity': True,
            'number_installments': quantidade_parcelas,
            'amount_contracted': valor_saque,
            'interest_fee': float(produto_convenio.taxa_produto),
            'contract_date': str(criacao_do_contrato),
            'first_due_date': str(data_vencimento),
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': auth,
        }
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        if 'error' in response_data:
            RetornosDock.objects.create(
                log_api_id=log_api.id,
                id_cliente=cliente.pk,
                payload=response.text,
                payload_envio=payload,
                nome_chamada='Simulação Saque Parcelado',
                codigo_retorno=response.status_code,
            )
            logger.error(
                f"Erro na simulação do saque parcelado do cliente {cliente}: {response_data['error']}",
                exc_info=True,
            )
            return {'Erro': 'Erro na simulação do saque parcelado junto a Dock'}
        else:
            logger.info({
                'corte': f'- Simulacao saque parcelado dock {corte}',
                'venciment_fatura': f'- Simulacao saque parcelado dock {vencimento_fatura}',
                'ciracao_do_contrato': f'{criacao_do_contrato}',
                'data_vencimento': f'{data_vencimento}',
            })
            # Reformatar o objeto datetime para o formato 'dd/mm/aaaa'
            data_formatada = data_vencimento.strftime('%d/%m/%Y')  # se here
            # Aqui estamos lidando com a resposta de sucesso
            valor_total_a_pagar = float(response_data['installment_value'])
            valor_total_a_pagar = round(valor_total_a_pagar, 4)
            return {
                'valor_solicitado_saque_parcelado': valor_saque,
                'valor_iof_total_em_dinheiro': response_data['total_iof'],
                'valor_total_financiado': response_data['financed_amount'],
                'valor_total_a_pagar': round(
                    response_data['installment_value'] * int(quantidade_parcelas),
                    4,
                ),
                'valor_parcela': response_data['installment_value'],
                'qtd_parcela': response_data['number_installments'],
                'taxa_produto': round(produto_convenio.taxa_produto, 4),
                'taxa_anual_produto': round(
                    ((1 + produto_convenio.valor_taxa_produto) ** (365 / 30)) - 1,
                    4,
                )
                * 100,
                'taxa_iof_diario': parametros_backoffice.taxa_iof_diario,
                'taxa_iof_adicional': parametros_backoffice.taxa_iof_adicional,
                'cet_anual': response_data['annual_cet'],
                'cet_mensal': response_data['month_cet'],
                'vencimento_primeira_parcela': str(data_formatada),
            }
    except Exception as e:
        RetornosDock.objects.create(
            log_api_id=log_api.id,
            id_cliente=cliente.pk,
            payload=e,
            nome_chamada='Simulação Saque Parcelado',
            codigo_retorno='400',
        )
        logger.error(
            f'Erro ao simular saque parcelado do cliente {cliente}, {e}', exc_info=True
        )
        return {'Erro': 'Erro na simulação do saque parcelado junto a Dock'}
