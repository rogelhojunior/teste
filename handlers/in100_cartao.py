import json
import logging
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from api_log.models import CancelaReserva, LogCliente, LogIn100, RealizaReserva
from contract.constants import EnumContratoStatus, EnumTipoProduto, NomeAverbadoras
from contract.models.contratos import CartaoBeneficio
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.Simulacao import Simulacao
from core import tasks
from core.common.enums import EnvironmentEnum
from core.models import Cliente, ParametrosBackoffice
from core.models.aceite_in100 import AceiteIN100
from core.models.cliente import ClienteCartaoBeneficio, ClienteInss
from core.utils import alterar_status
from handlers.dock_consultas import simulacao_saque_parcelado_dock
from handlers.zenvia_sms import zenvia_sms

logger = logging.getLogger('digitacao')

url = settings.HUB_AVERBADORA_URL


def autorizacao_consulta_digital(
    cpf_cliente,
    canal_autorizacao_digital,
    aceite_in100,
    averbadora,
    codigo_convenio,
):
    cliente = Cliente.objects.get(nu_cpf=cpf_cliente)

    try:
        data_auth_formatted = aceite_in100.data_aceite.strftime('%d%m%Y%H%M%S')

        payload = json.dumps({
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'autorizacaoConsultaDigital',
            },
            'parametrosBackoffice': {'senhaAdmin': '', 'usuario': '', 'url': ''},
            'canal': {'canalAutorizacaoDigital': canal_autorizacao_digital},
            'cliente': {
                'nuCpf': f'{cpf_cliente}',
                'nsuAutorizacaoDigital': aceite_in100.pk,
                'dataHoraAutorizacaoDigital': data_auth_formatted,
            },
        })
        headers = {'Content-Type': 'application/json'}

        response = requests.request('POST', url, headers=headers, data=payload)
        # Remove as sequências de escape e as aspas duplas extras do início e do fim
        response_text = response.text.replace('\\', '').strip('"')
        response_dict = json.loads(response_text)

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        LogIn100.objects.update_or_create(
            log_api=log_api_id,
            cliente=cliente,
            payload_envio=payload,
            payload=response_dict,
            tipo_chamada='Autorizacao Consulta Digital',
        )

        aceite_in100.token_in100 = response_dict['tokenAutorizacao']
        aceite_in100.data_vencimento_token = response_dict['dataValidadeAutorizacao']
        aceite_in100.data_criacao_token = date.today()
        aceite_in100.canal_autorizacao_digital = canal_autorizacao_digital
        aceite_in100.save()
        logger.info(f'{cpf_cliente} - Consulta digital autorizada', exc_info=True)
        return response_dict

    except Exception as e:
        logger.error(
            f'{cpf_cliente} - Erro ao autorizar consulta digital. {e}', exc_info=True
        )


def consulta_beneficio(cpf_cliente, tokenAutorizacao, averbadora):
    cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
    try:
        payload = json.dumps({
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'consultaBeneficio',
            },
            'parametrosBackoffice': {'senhaAdmin': '', 'usuario': '', 'url': ''},
            'cliente': {
                'nuCpf': f'{cpf_cliente}',
                'tokenAutorizacao': f'{tokenAutorizacao}',
            },
        })
        headers = {'Content-Type': 'application/json'}

        response = requests.request('POST', url, headers=headers, data=payload)
        # Remove as sequências de escape e as aspas duplas extras do início e do fim
        response_text = response.text.replace('\\', '').strip('"')
        response_dict = json.loads(response_text)

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
        LogIn100.objects.update_or_create(
            log_api=log_api_id,
            cliente=cliente,
            payload_envio=payload,
            payload=response_dict,
            tipo_chamada='Consulta Benefícios',
        )

        logger.info(f'{cpf_cliente} - Beneficios consultados', exc_info=True)

        return 'Erro Tecnico' if response_dict == [] else response_dict
    except Exception as e:
        print(e)
        logger.error(f'{cpf_cliente} - Erro ao consultar beneficios.', exc_info=True)
        return 'Erro Tecnico'


def consulta_margem_inss(
    cpf_cliente,
    tokenAutorizacao,
    averbadora,
    numero_beneficio,
    contrato=None,
    contrato_cartao=None,
):
    cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
    try:
        payload = json.dumps({
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'consultaMargemInss',
            },
            'parametrosBackoffice': {'senhaAdmin': '', 'usuario': '', 'url': ''},
            'cliente': {
                'nuCpf': f'{cpf_cliente}',
                'tokenAutorizacao': f'{tokenAutorizacao}',
                'numeroBeneficio': f'{numero_beneficio}',
            },
        })
        headers = {'Content-Type': 'application/json'}

        response = requests.request('POST', url, headers=headers, data=payload)
        # Remove as sequências de escape e as aspas duplas extras do início e do fim
        response_text = response.text.replace('\\', '').strip('"')
        response_dict = json.loads(response_text)
        if contrato:
            if contrato.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
                margem = Decimal(str(response_dict.get('margemDisponivelRCC')))
                tipo_margem = 'Cartão Benefício'
            elif contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                margem = Decimal(str(response_dict.get('margemDisponivelCartao')))
                tipo_margem = 'Cartão Consignado'

            new_response_dict = [
                {
                    'numeroBeneficio': response_dict.get('numeroBeneficio'),
                    'cpf': response_dict.get('cpf'),
                    'dataNascimento': '13/12/1994',  # response_dict.get("dataNascimento")
                    'nomeBeneficiario': response_dict.get('nomeBeneficiario'),
                    'especieBeneficio': response_dict.get('especieBeneficio'),
                    'ufPagamento': response_dict.get('ufPagamento'),
                    'tipoCredito': response_dict.get('tipoCredito'),
                    'cbcIfPagadora': response_dict.get('cbcIfPagadora'),
                    'agenciaPagadora': response_dict.get('agenciaPagadora'),
                    'contaCorrente': response_dict.get('contaCorrente'),
                    'possuiRepresentanteLegal': response_dict.get(
                        'possuiRepresentanteLegal'
                    ),
                    'possuiProcurador': response_dict.get('possuiProcurador'),
                    'possuiEntidadeRepresentacao': response_dict.get(
                        'possuiEntidadeRepresentacao'
                    ),
                    'tipoMargem': tipo_margem,
                    'margemDisponivel': margem,
                    'folha': str(response_dict['especieBeneficio']['codigo'])
                    + '-'
                    + str(response_dict['especieBeneficio']['descricao']),
                },
            ]
        else:
            margem_rcc = Decimal(str(response_dict.get('margemDisponivelRCC')))
            margem_cartao = Decimal(str(response_dict.get('margemDisponivelCartao')))

            new_response_dict = [
                {
                    'numeroBeneficio': response_dict.get('numeroBeneficio'),
                    'cpf': response_dict.get('cpf'),
                    'dataNascimento': '13/12/1994',  # response_dict.get("dataNascimento")
                    'nomeBeneficiario': response_dict.get('nomeBeneficiario'),
                    'especieBeneficio': response_dict.get('especieBeneficio'),
                    'ufPagamento': response_dict.get('ufPagamento'),
                    'tipoCredito': response_dict.get('tipoCredito'),
                    'cbcIfPagadora': response_dict.get('cbcIfPagadora'),
                    'agenciaPagadora': response_dict.get('agenciaPagadora'),
                    'contaCorrente': response_dict.get('contaCorrente'),
                    'possuiRepresentanteLegal': response_dict.get(
                        'possuiRepresentanteLegal'
                    ),
                    'possuiProcurador': response_dict.get('possuiProcurador'),
                    'possuiEntidadeRepresentacao': response_dict.get(
                        'possuiEntidadeRepresentacao'
                    ),
                    'tipoMargem': 'Cartão Benefício',
                    'margemDisponivel': margem_rcc,
                    'folha': str(response_dict['especieBeneficio']['codigo'])
                    + '-'
                    + str(response_dict['especieBeneficio']['descricao']),
                },
                {
                    'numeroBeneficio': response_dict.get('numeroBeneficio'),
                    'cpf': response_dict.get('cpf'),
                    'dataNascimento': '13/12/1994',  # response_dict.get("dataNascimento")
                    'nomeBeneficiario': response_dict.get('nomeBeneficiario'),
                    'especieBeneficio': response_dict.get('especieBeneficio'),
                    'ufPagamento': response_dict.get('ufPagamento'),
                    'tipoCredito': response_dict.get('tipoCredito'),
                    'cbcIfPagadora': response_dict.get('cbcIfPagadora'),
                    'agenciaPagadora': response_dict.get('agenciaPagadora'),
                    'contaCorrente': response_dict.get('contaCorrente'),
                    'possuiRepresentanteLegal': response_dict.get(
                        'possuiRepresentanteLegal'
                    ),
                    'possuiProcurador': response_dict.get('possuiProcurador'),
                    'possuiEntidadeRepresentacao': response_dict.get(
                        'possuiEntidadeRepresentacao'
                    ),
                    'tipoMargem': 'Cartão Consignado',
                    'margemDisponivel': margem_cartao,
                    'folha': str(response_dict['especieBeneficio']['codigo'])
                    + '-'
                    + str(response_dict['especieBeneficio']['descricao']),
                },
            ]

        in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
        in100.cbc_if_pagadora = new_response_dict[0]['cbcIfPagadora']
        in100.agencia_pagadora = new_response_dict[0]['agenciaPagadora']
        in100.conta_corrente = new_response_dict[0]['contaCorrente']
        in100.UFAPS = new_response_dict[0]['ufPagamento']
        if new_response_dict[0]['contaCorrente']:
            DV_conta_corrente = new_response_dict[0]['contaCorrente'][-1] or ''
        else:
            DV_conta_corrente = ''

        in100.DV_conta_corrente = DV_conta_corrente
        in100.nome_cliente = new_response_dict[0]['nomeBeneficiario']
        in100.save()

        cliente_inss, _ = ClienteInss.objects.get_or_create(cliente=cliente)
        cliente_inss.nome_beneficio = new_response_dict[0]['especieBeneficio'][
            'descricao'
        ]
        cliente_inss.nu_beneficio = new_response_dict[0]['numeroBeneficio']
        cliente_inss.uf_beneficio = new_response_dict[0]['ufPagamento']
        cliente_inss.save()

        if contrato and contrato_cartao and contrato_cartao.convenio.digitacao_manual:
            cliente_cartao, _ = ClienteCartaoBeneficio.objects.get_or_create(
                cliente=cliente,
                tipo_produto=contrato.tipo_produto,
                convenio=contrato_cartao.convenio,
                contrato=contrato,
            )
            try:
                if new_response_dict[0]['tipoCredito'] in (2, '2'):
                    cliente_dados_bancarios = cliente.cliente_dados_bancarios.last()
                    cliente_dados_bancarios.conta_agencia = new_response_dict[0][
                        'agenciaPagadora'
                    ]
                    cliente_dados_bancarios.conta_numero = new_response_dict[0][
                        'contaCorrente'
                    ]
                    cliente_dados_bancarios.conta_digito = DV_conta_corrente
                    cliente_dados_bancarios.conta_banco = new_response_dict[0][
                        'cbcIfPagadora'
                    ]
                    cliente_dados_bancarios.save()
            except Exception as e:
                logger.error(e)
            contrato_saque_parcelado = False
            possui_saque = False

            if contrato_cartao.possui_saque:
                if contrato_cartao.saque_parcelado:
                    contrato_saque_parcelado = True
                possui_saque = True
            elif contrato_cartao.saque_parcelado:
                contrato_saque_parcelado = True
                possui_saque = True

            # TODO: Remove card paradinha feature flag
            should_go_to_corban_desk = (
                contrato.corban.mesa_corban
                and settings.ENVIRONMENT != EnvironmentEnum.PROD.value
            )
            next_status = (
                ContractStatus.CHECAGEM_MESA_CORBAN
                if should_go_to_corban_desk
                else ContractStatus.CHECAGEM_MESA_FORMALIZACAO
            )

            if cliente_cartao.margem_atual == margem:
                alterar_status(
                    contrato,
                    contrato_cartao,
                    EnumContratoStatus.MESA,
                    next_status.value,
                )
                resultado = None
            elif Decimal(str(margem)) > cliente_cartao.margem_atual:
                simulador = Simulacao(
                    contrato_cartao.convenio.pk,
                    contrato.tipo_produto,
                    cliente.dt_nascimento,
                    margem,
                    cliente.nu_cpf,
                    cliente_cartao.pk,
                )
                resultado = simulador.realizar(possui_saque=possui_saque)
                if 'error' in resultado:
                    return 'Erro Simulacao', resultado

                contrato.limite_pre_aprovado = resultado[0]['limite_pre_aprovado']
                contrato_cartao.valor_disponivel_saque = resultado[1][
                    'valor_maximo_saque'
                ]
                contrato_cartao.folha = new_response_dict[0]['especieBeneficio'][
                    'codigo'
                ]
                cliente_cartao.folha = new_response_dict[0]['especieBeneficio'][
                    'codigo'
                ]
                cliente_cartao.margem_atual = margem

                alterar_status(
                    contrato,
                    contrato_cartao,
                    EnumContratoStatus.MESA,
                    next_status.value,
                )
            elif Decimal(str(margem)) < cliente_cartao.margem_atual:
                diferenca_percentual = (
                    (cliente_cartao.margem_atual - margem)
                    / cliente_cartao.margem_atual
                    * 100
                )
                if (
                    diferenca_percentual
                    <= contrato_cartao.convenio.porcentagem_reducao_margem
                ):
                    simulador = Simulacao(
                        contrato_cartao.convenio.pk,
                        contrato.tipo_produto,
                        cliente.dt_nascimento,
                        margem,
                        cliente.nu_cpf,
                        cliente_cartao.pk,
                    )
                    resultado = simulador.realizar(possui_saque=possui_saque)
                    if 'error' in resultado:
                        return 'Erro Simulacao', resultado
                    contrato.limite_pre_aprovado = resultado[0]['limite_pre_aprovado']
                    contrato_cartao.valor_disponivel_saque = resultado[1][
                        'valor_maximo_saque'
                    ]
                    contrato_cartao.folha = new_response_dict[0]['especieBeneficio'][
                        'codigo'
                    ]
                    cliente_cartao.folha = new_response_dict[0]['especieBeneficio'][
                        'codigo'
                    ]
                    cliente_cartao.margem_atual = margem

                    contrato_cartao.valor_saque = min(
                        contrato_cartao.valor_saque,
                        contrato_cartao.valor_disponivel_saque,
                    )
                    if contrato_saque_parcelado:
                        parametros_backoffice = ParametrosBackoffice.objects.filter(
                            ativo=True, tipoProduto=contrato.tipo_produto
                        ).first()
                        simulacao_saque_parcelado = simulacao_saque_parcelado_dock(
                            contrato_cartao.qtd_parcela_saque_parcelado,
                            contrato_cartao.valor_saque,
                            contrato_cartao.convenio,
                            cliente,
                            parametros_backoffice,
                        )
                        contrato_cartao.valor_parcela = simulacao_saque_parcelado[
                            'valor_parcela'
                        ]
                        contrato_cartao.valor_total_a_pagar = simulacao_saque_parcelado[
                            'valor_total_a_pagar'
                        ]
                        contrato_cartao.valor_financiado = simulacao_saque_parcelado[
                            'valor_total_financiado'
                        ]
                        contrato.cet_mes = simulacao_saque_parcelado['cet_mensal']
                        contrato.cet_ano = simulacao_saque_parcelado['cet_anual']
                        valor_liquido = (
                            Decimal(str(response_dict.get('valorComprometido')))
                            + margem
                        )
                        mensagem = (
                            f'{cliente.nome_cliente}, de acordo com a analise da margem do seu benefício, o limite '
                            f'pre-aprovado do seu cartão foi ajustado para {contrato.limite_pre_aprovado} e seu limite de saque para '
                            f'{contrato_cartao.valor_disponivel_saque}. O valor liquido do seu beneficio após aprovação do contrato, '
                            f'sera de {valor_liquido}. Para mais informacoes, contate seu correspondente'
                        )
                        zenvia_sms(cliente.nu_cpf, cliente.telefone_celular, mensagem)
                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.MESA,
                        next_status.value,
                    )
                else:
                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.CANCELADO,
                        ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                        observacao=f'A margem do contrato é superior a margem retornada da Dataprev. Valor retornado: R$ {margem}',
                    )
                    resultado = None
            contrato.save()
            contrato_cartao.save()
            cliente_cartao.save()

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        LogIn100.objects.update_or_create(
            log_api=log_api_id,
            cliente=cliente,
            payload_envio=payload,
            payload=response_dict,
            tipo_chamada='Consulta Margem',
        )

        logger.info(f'{cpf_cliente} - Margem consultada', exc_info=True)
        if contrato and contrato_cartao and contrato_cartao.convenio.digitacao_manual:
            return response_dict, resultado
        else:
            return new_response_dict, response_dict
    except Exception as e:
        print(e)
        logger.error(f'{cpf_cliente} - Erro ao consultar margem.', exc_info=True)
        return 'Erro Tecnico', ''


def reserva_margem_inss(cpf_cliente, averbadora, contrato, margem):
    cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
    in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
    cliente_inss = ClienteInss.objects.get(cliente=cliente)
    data_aprovacao = date.today()
    data_aprovacao_formatada = data_aprovacao.strftime('%d%m%Y')
    valor_limte_cartao = round(contrato.limite_pre_aprovado, 2)
    valor_limte_cartao = float(valor_limte_cartao)
    cnpj = (
        contrato.corban.corban_CNPJ.replace('.', '').replace('-', '').replace('/', '')
    )
    if in100.DV_conta_corrente == '':
        conta = cliente.cliente_dados_bancarios.last()
        DV_conta_corrente = conta.conta_digito
        conta_corrente = conta.conta_numero
    else:
        DV_conta_corrente = in100.DV_conta_corrente
        conta_corrente = in100.conta_corrente
    payload = json.dumps({
        'averbadora': {
            'nomeAverbadora': averbadora,
            'operacao': 'reservaMargemInss',
        },
        'parametrosBackoffice': {'senhaAdmin': '', 'usuario': '', 'url': ''},
        'canal': {'canalAutorizacaoDigital': in100.canal},
        'cliente': {
            'nuCpf': f'{cliente.nu_cpf}',
            'numeroBeneficio': f'{cliente_inss.nu_beneficio}',
            'nomeCliente': f'{in100.nome_cliente}',
        },
        'contrato': {
            'idContrato': contrato.pk,
            'dataAprovacaoContrato': f'{data_aprovacao_formatada}',
            'cbcIfPagadora': in100.cbc_if_pagadora,
            'agenciaPagadora': in100.agencia_pagadora,
            'contaCorrente': f'{conta_corrente}',
            'valorLimiteCartao': valor_limte_cartao,
            'percentualRCC': 5,  # Uma incognita, mas 5 funciona
            'UFAPS': f'{in100.UFAPS}',
            'DVContaCorrente': f'{DV_conta_corrente}',
            'CNPJCorrespondente': cnpj,
            'CPFCorrespondente': contrato.created_by.identifier,
        },
    })

    headers = {'Content-Type': 'application/json'}

    response = requests.request('POST', url, headers=headers, data=payload)
    # Remove as sequências de escape e as aspas duplas extras do início e do fim
    response_text = response.text.replace('\\', '').strip('"')
    response_dict = json.loads(response_text)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    LogIn100.objects.update_or_create(
        log_api=log_api_id,
        cliente=cliente,
        payload_envio=payload,
        payload=response_dict,
        tipo_chamada='Reservar Margem',
    )
    try:
        if response_dict['codigoSucesso'] == 'BD':
            contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
            contrato_cartao.reserva = response_dict['hashOperacao']
            contrato_cartao.save(update_fields=['reserva'])
            contrato_cartao.refresh_from_db()
            realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                valor=response_dict['valorReservado'],
                reserva=response_dict['hashOperacao'],
                codigo_retorno=response_dict['codigoSucesso'],
            )

            logger.info(f'{cpf_cliente} - Reserva realizada - INSS', exc_info=True)

            # Caso a reserva seja realizada com sucesso, e a averbadora for a PINE, enviar informacoes adicionais
            tasks.envia_info_inss_pine.delay(contrato.pk)

        else:
            realiza_reserva_obj = RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_dict['mensagem'],
                codigo_retorno=response_dict['codigoSucesso'],
            )

            logger.error(
                f'{cpf_cliente} - Erro ao resevar margem - INSS.', exc_info=True
            )

    except Exception as e:
        print(e)
        realiza_reserva_obj = RealizaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_dict['erros'][0]['mensagem'],
            codigo_retorno=response_dict['erros'][0]['codigo'],
        )

        logger.error(f'{cpf_cliente} - Erro ao resevar margem - INSS.', exc_info=True)

    return realiza_reserva_obj


def cancela_reserva_dataprev_pine(cpf_cliente, averbadora, contrato):
    cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
    cliente_cartao_beneficio = contrato.cliente_cartao_contrato.get()

    payload = json.dumps({
        'averbadora': {
            'nomeAverbadora': averbadora,
            'operacao': 'cancelaMargemInss',
        },
        'contrato': {
            'idContrato': contrato.pk,
        },
        'cliente': {
            'numeroBeneficio': cliente_cartao_beneficio.numero_matricula,
        },
    })

    headers = {'Content-Type': 'application/json'}

    response = requests.request('POST', url, headers=headers, data=payload)
    # Remove as sequências de escape e as aspas duplas extras do início e do fim
    response_text = response.text.replace('\\', '').strip('"')
    response_dict = json.loads(response_text)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    LogIn100.objects.update_or_create(
        log_api=log_api_id,
        cliente=cliente,
        payload_envio=payload,
        payload=response_dict,
        tipo_chamada='Cancelar Margem',
    )

    try:
        numero_matricula = response_text['numeroMatricula']
        cancelada = True

        cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=numero_matricula,
            cancelada=cancelada,
        )

    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao cancelar reserva {averbadora} - {e}.',
            exc_info=True,
        )
        cancela_reserva_obj = CancelaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_dict['descontosCartaoFalha'][0]['erros'][0]['mensagem'],
            codigo_retorno=response_dict['descontosCartaoFalha'][0]['erros'][0][
                'codigo'
            ],
        )

    return cancela_reserva_obj


def incluir_desconto_cartao(payload):
    payload = json.dumps({
        'averbadora': {
            'nomeAverbadora': NomeAverbadoras.DATAPREV_PINE.value,
            'operacao': 'incluirDescontoCartao',
        },
        'parametrosBackoffice': {'senhaAdmin': '', 'usuario': '', 'url': ''},
        'cliente': {
            'nuCpf': '',
            'tokenAutorizacao': '',
        },
        'payloadInclusaoDesconto': payload,
    })
    headers = {'Content-Type': 'application/json'}
    return requests.request('POST', url, headers=headers, data=payload)
