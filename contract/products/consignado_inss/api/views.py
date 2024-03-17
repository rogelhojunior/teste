import logging
import traceback
from datetime import datetime, timedelta

import newrelic.agent
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.views import APIView

from api_log.models import LogCliente, QitechRetornos
from contract.constants import EnumContratoStatus
from contract.models.contratos import Contrato, MargemLivre
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.api.serializers import (
    AtualizarContratoMargemLivreSerializer,
    AtualizarMargemLivreSerializer,
)
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.utils import calcular_diferenca_datas
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialFreeMargin,
)
from core import settings
from core.models import BancosBrasileiros
from custom_auth.models import UserProfile
from handlers.insere_proposta_inss_financeira import insere_proposta_inss_financeira_hub
from handlers.qitech_api.utils import decrypt
from handlers.receber_webhook_qitech import obter_margem_cliente
from handlers.simulacao_inss import simulacao_hub_inss
from handlers.webhook_qitech import (
    atualiza_contrato_webhook,
)
from simulacao.communication import qitech
from simulacao.utils import convert_string_to_date_yyyymmdd, data_atual_sem_hora
from utils.bank import get_client_bank_data

logger = logging.getLogger('digitacao')


class insere_proposta_inss_financeira(GenericAPIView):
    def post(self, request):
        try:
            token_contrato = request.data['token']
            insere_proposta_inss_financeira_hub(
                token_contrato, 0.01, 'calendar_days', 0.02
            )
            return Response('CCB Gerada com sucesso.', status=HTTP_200_OK)

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {
                    'Erro': 'Não foi possível realizar inclusão da proposta na financeira.'
                },
                status=HTTP_400_BAD_REQUEST,
            )


class RealizaSimulacao(GenericAPIView):
    """
    API para chamada do hub e realização da simulação vinculada à QiTech
    """

    def post(self, request):
        # dados do request : numero_cpf, dt_nascimento, tipo_contrato, codigo_beneficio,
        # numero_beneficio, margem_livre, valor_parcela, valor_contrato
        try:
            dados_simulacao = request.data
            # cliente = consulta_cliente(dados_simulacao['numero_cpf'])
            numero_beneficio = dados_simulacao['numero_beneficio']
            if DadosIn100.objects.filter(numero_beneficio=numero_beneficio).exists():
                in100 = DadosIn100.objects.filter(
                    numero_beneficio=numero_beneficio
                ).first()
                if in100.retornou_IN100:
                    dados_simulacao['margem_livre'] = in100.valor_margem
                    if (
                        dados_simulacao['margem_livre']
                        < dados_simulacao['valor_parcela']
                    ):
                        dados_simulacao['valor_parcela'] = dados_simulacao[
                            'margem_livre'
                        ]
            simulacao_obj = simulacao_hub_inss(**dados_simulacao)
            if simulacao_obj['retornado']:
                return Response(simulacao_obj['simulacao_obj'], status=HTTP_200_OK)
            else:
                return Response(
                    'Erro ao realizar a SIMULAÇÃO verifique com um administrador',
                    status=HTTP_400_BAD_REQUEST,
                )

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


class ReceberWebhookQitech(APIView):
    """
    API para processamento do webhook de retorno da QiTech
    """

    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            str_json_encriptado = request.data['encoded_body']
            json_obj = decrypt(str_json_encriptado)
            atualiza_contrato_webhook(json_obj, request.user)

            return Response(
                {'Ok': 'Webhook processado com sucesso.'}, status=HTTP_200_OK
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                msg='Something wrong when processing the QiTech webhook return.',
                extra={'request_data': request.data},
            )
            traceback.print_exc()
            newrelic.agent.notice_error()
            raise ValidationError(
                detail={'Erro': 'Não foi possível processar o webhook.'},
                # TODO: Deveria ser um HTTP_500_INTERNAL_SERVER_ERROR
                code=HTTP_400_BAD_REQUEST,
            ) from e


class ObterMargemCliente(APIView):
    """
    API para obter a margem do cliente
    """

    def post(self, request):
        try:
            json_obj = request.data

            nu_cpf = json_obj['NuCpf']

            objMargem = obter_margem_cliente(nu_cpf)

            return Response(objMargem, status=HTTP_200_OK)

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi obter a margem do cliente informado.'},
                status=HTTP_400_BAD_REQUEST,
            )


class AtualizarContratoMargemLivre(UpdateAPIView):
    """
    Atualização de contratos Margem Livre e seus status.
    """

    def patch(self, request):
        payload = request.data
        token_contrato = request.data['token_contrato']
        contrato = Contrato.objects.get(token_contrato=token_contrato)
        consig_margem_livre = MargemLivre.objects.get(contrato=contrato)
        serializer = AtualizarContratoMargemLivreSerializer(
            contrato, data=payload, partial=True
        )
        margem_livre_serializer = AtualizarMargemLivreSerializer(
            consig_margem_livre, data=payload, partial=True
        )
        #  Validar flag de pendente antes de analisar/atualizar contrato
        if serializer.is_valid() and margem_livre_serializer.is_valid():
            try:
                contrato_set = serializer.save()
                margem_livre_set = margem_livre_serializer.save()

                if contrato_set and margem_livre_set:
                    contrato.status = EnumContratoStatus.DIGITACAO
                    consig_margem_livre.status = (
                        ContractStatus.ANDAMENTO_SIMULACAO.value
                    )
                    consig_margem_livre.save()
                    contrato.save()
                    ultimo_status = StatusContrato.objects.filter(
                        contrato=contrato
                    ).last()
                    if ultimo_status.nome != ContractStatus.ANDAMENTO_SIMULACAO.value:
                        user = UserProfile.objects.get(
                            identifier=request.user.identifier
                        )
                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=ContractStatus.ANDAMENTO_SIMULACAO.value,
                            created_by=user,
                        )
                    return Response(
                        {'msg': 'Contrato atualizado com sucesso.'}, status=HTTP_200_OK
                    )
            except Exception as e:
                logger.error(
                    f'Erro ao realizar a chamada (AtualizarContratoMargemLivre): {e}'
                )
                return Response(
                    {
                        'msg': 'Ocorreu um erro ao realizar a chamada, contate o suporte.'
                    },
                    status=HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            errors = {
                'contrato_errors': None if serializer.is_valid() else serializer.errors,
                'margem_livre_errors': (
                    None
                    if margem_livre_serializer.is_valid()
                    else margem_livre_serializer.errors
                ),
            }
            return Response(
                {'msg': 'Não foi possivel atualizar o contrato.', 'errors': errors},
                status=HTTP_400_BAD_REQUEST,
            )


class ReapresentacaoPagamentoMargemLivre(UpdateAPIView):
    """
    Reapresentação de pagamentos de MArgem Livre
    """

    def post(self, request):
        contrato = self._obter_contrato(request.data['token_contrato'])
        try:
            margem_livre = self._obter_margem_livre(contrato)
            cliente_dados_bancarios = get_client_bank_data(client=contrato.cliente)
            banco_do_cliente = self._validar_banco(cliente_dados_bancarios)
            user = request.user
            corpo_requisicao = self._preparar_corpo_requisicao(
                margem_livre, cliente_dados_bancarios, contrato, banco_do_cliente
            )

            json_retorno, status_code = self._executar_requisicao_qitech(
                margem_livre, corpo_requisicao
            )
            return self._processar_resposta_qitech(
                contrato, json_retorno, status_code, margem_livre, user
            )

        except Exception as e:
            return self._gerar_resposta_erro(contrato, e)

    def _obter_contrato(self, token_contrato):
        return Contrato.objects.get(token_contrato=token_contrato)

    def _obter_margem_livre(self, contrato):
        margem_livre = MargemLivre.objects.filter(contrato=contrato).first()
        if not margem_livre.dt_averbacao:
            raise ValueError(
                'Não foi possivel realizar a reapresentação do pagamento pois ele ainda não foi averbado.'
            )
        self._validar_data_limite(margem_livre.dt_averbacao, contrato)
        return margem_livre

    def _validar_data_limite(self, dt_averbacao, contrato):
        hoje = datetime.now()
        anos, meses, dias = calcular_diferenca_datas(dt_averbacao, hoje)
        if anos > 0 or meses > 0 or dias > 10:
            if RefuseProposalFinancialFreeMargin(contrato).execute():
                raise ValueError(
                    'Não foi possivel realizar a reapresentação do pagamento pois ja se passaram os 10 dias de reapresentação.'
                )
            else:
                raise ValueError(
                    'Não foi possivel realizar a reapresentação do pagamento pois ja se passaram os 10 dias de reapresentação,'
                    ' aguardando desaverbação.'
                )

    def _validar_banco(self, cliente_dados_bancarios):
        banco = BancosBrasileiros.objects.filter(
            codigo=cliente_dados_bancarios.conta_banco
        )
        if not banco.exists():
            raise ValueError(
                'Não foi possivel realizar a reapresentação do pagamento pois Banco do cliente não encontrado.'
            )
        return banco.first()

    def _preparar_corpo_requisicao(
        self, margem_livre, cliente_dados_bancarios, contrato, banco_do_cliente
    ):
        data_desembolso = convert_string_to_date_yyyymmdd(data_atual_sem_hora())
        # Validate if hour from localtime (GMT -03:00) is lower than 17
        if timezone.localtime().hour < 17:
            nova_data_desembolso = data_desembolso.isoformat()
        else:
            nova_data_desembolso = self._adicionar_dia_na_data(str(data_desembolso))
        margem_livre.dt_desembolso = nova_data_desembolso
        margem_livre.save()
        cpf_formatado = cliente_dados_bancarios.conta_cpf_titular.replace(
            '.', ''
        ).replace('-', '')

        return {
            'disbursement_date': str(nova_data_desembolso),
            'disbursement_bank_accounts': [
                {
                    'branch_number': f'{str(cliente_dados_bancarios.conta_agencia)}',
                    'account_digit': f'{str(cliente_dados_bancarios.conta_digito)}',
                    'account_number': f'{str(cliente_dados_bancarios.conta_numero)}',
                    'account_type': 'checking_account',
                    'document_number': f'{str(cpf_formatado)}',
                    'bank_code': f'{str(cliente_dados_bancarios.conta_banco)}',
                    'ispb_number': f'{str(banco_do_cliente.ispb)}',
                    'name': f'{str(contrato.cliente.nome_cliente)}',
                    'percentage_receivable': 100,
                }
            ],
        }

    def _executar_requisicao_qitech(self, margem_livre, corpo_requisicao):
        QITECH_ENDPOINT_DEBT_DESAVERBACAO = (
            f'/debt/{margem_livre.chave_proposta}/change_disbursement_date'
        )
        integracao_desaverbacao = qitech.QitechApiIntegration()
        return integracao_desaverbacao.execute(
            settings.QITECH_BASE_ENDPOINT_URL,
            QITECH_ENDPOINT_DEBT_DESAVERBACAO,
            corpo_requisicao,
            'POST',
        )

    def _processar_resposta_qitech(
        self, contrato, json_retorno, status_code, margem_livre, user
    ):
        if status_code in {200, 201, 202}:
            margem_livre.sucesso_reapresentacao_pagamento = True
            self._registrar_log(contrato, json_retorno, 'REAPRESENTAÇAO', success=True)
            margem_livre.status = ContractStatus.AGUARDANDO_DESEMBOLSO.value
            margem_livre.save()
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.AGUARDANDO_DESEMBOLSO.value,
                descricao_mesa='Reapresentado, AGUARDANDO DESEMBOLSO (MARGEM LIVRE)',
                created_by=user,
            )
            return Response(
                {'msg': 'Reapresentação do pagamento realizada'}, status=HTTP_200_OK
            )

        else:
            margem_livre.sucesso_reapresentacao_pagamento = False
            margem_livre.motivo_reapresentacao_pagamento = json_retorno['description']
            margem_livre.save()
            self._registrar_log(contrato, json_retorno, 'REAPRESENTAÇAO', success=False)
            raise ValueError(
                'Não             foi possivel reaalizar a reapresentação do pagamento, Contacte o Suporte.'
            )

    def _registrar_log(self, contrato, json_retorno, tipo, success=True):
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contrato.cliente,
            retorno=json_retorno,
            tipo=tipo,
        )
        if success:
            logger.info(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}) (Margem Livre) Reapresentado com sucesso.\n Payload {json_retorno}'
            )
        else:
            logger.error(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}) (Margem Livre) Erro na reapresentação do Pagamento.\n Payload {json_retorno}'
            )

    def _gerar_resposta_erro(self, contrato, erro):
        if isinstance(erro, ValueError):
            msg = str(erro)
        else:
            msg = 'Não foi possivel realizar a reapresentação do pagamento, contacte o Suporte.'
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
            QitechRetornos.objects.create(
                log_api_id=log_api_id.pk,
                cliente=contrato.cliente,
                retorno=str(erro),
                tipo='REAPRESENTAÇAO',
            )
            logger.error(
                f'{contrato.cliente.id_unico} - Contrato({contrato.pk}):'
                f' (Margem Livre) Erro ao realizar o cancelamento da proposta na QiTech.\n Payload {erro}'
            )
        return Response({'msg': msg}, status=HTTP_400_BAD_REQUEST)

    def _adicionar_dia_na_data(self, data_str, format_str='%Y-%m-%d'):
        date_obj = datetime.strptime(data_str, format_str)

        # Adicionando um dia
        nova_data = date_obj + timedelta(days=1)

        # Convertendo de volta para string
        nova_data = nova_data.strftime(format_str)

        return nova_data
