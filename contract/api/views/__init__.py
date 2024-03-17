import json
import logging
import re
from datetime import datetime, timedelta
from typing import Tuple

import newrelic.agent
from celery import chain
from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Avg, Q
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from import_export.formats import base_formats
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.views import APIView
from contract.models.regularizacao_contrato import RegularizacaoContrato
from contract.models.tentativa_teimosinha_inss import TentativaTeimosinhaINSS
from core.common.enums import EnvironmentEnum
from rest_framework_api_key.permissions import HasAPIKey
from slugify import slugify

import contract.api.serializers as api_contrato
from contract.admin import contrato_resource_export
from contract.api.serializers import (
    PendingRegistrationRegularizationRequestSerializer,
    StatusContratoSerializer,
    StubbornINSSHistoryRequestSerializer,
    TentativaTeimosinhaINSSSerializer,
)
from contract.api.serializers.typist_serializer import TypistSerializer
from contract.constants import (
    EnumContratoStatus,
    EnumTipoAnexo,
    EnumTipoProduto,
    NomeAverbadoras,
    EnumEscolaridade,
)
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
    RetornoSaque,
    SaqueComplementar,
)
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import Convenios
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.especie import EspecieIN100
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    SubmitFinancialPortabilityProposal,
)
from contract.services.payment.payment_manager import PaymentManager
from contract.services.validators.score_validation import ScoreValidation
from contract.utils import (
    get_subordinate_ids_at_all_levels,
    get_viewable_contracts,
    mesa_corban_contracts,
    corban_master_contracts,
)
from contract.views import link_formalizacao_envelope
from core.constants import EnumNivelHierarquia
from core.models import ParametrosBackoffice
from core.models.cliente import Cliente
from core.serializers import IN100Serializer
from core.settings import ENVIRONMENT
from core.utils import alterar_status
from custom_auth.models import Produtos, UserProfile
from documentscopy.services import BPOProcessor, analyse_cpf
from handlers.banksoft import comissionamento_banksoft
from handlers.brb import atualizacao_cadastral, envio_dossie, retorno_saque
from handlers.dock_consultas import limites_disponibilidades
from handlers.dock_formalizacao import (
    ajustes_financeiros,
    criar_individuo_dock,
    lancamento_saque_parcelado_fatura,
)
from handlers.facil import realiza_reserva
from handlers.in100_cartao import reserva_margem_inss
from handlers.modifica_proposta_portabilidade import (
    modifica_proposta_portabilidade_financeira_hub,
)
from handlers.quantum import reservar_margem_quantum
from handlers.serpro import Serpro
from handlers.submete_proposta_portabilidade import (
    submete_proposta_portabilidade_financeira_hub,
)
from handlers.webhook_qitech import salvando_retorno_IN100_contrato
from handlers.zetra import Zetra, reservar_margem_zetra
from contract.api.serializers import UnicoCallbackSerializer
from rest_framework.parsers import JSONParser

from utils.pagination import get_pagination_data, paginate

logger = logging.getLogger('digitacao')
logger_detail_contract = logging.getLogger('detalhe-contrato')


class ListarContratos(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_contract_filters(self, query_params: dict) -> dict:
        """
        Recebe um dicionário de filtros e cria cada filtro necessário para filtrar os contratos
        !TODO Trocar pela lib django_filters!! e refatorar a listagem para o serializer.
        :param query_params: Dicionário com os filtros para serem verificados
        :return: Um dicionário com os filtros a serem aplicados, traduzidos para o ORM
        """
        numero_contrato = query_params.get('contrato')
        cpf = query_params.get('cpf')
        nome_cliente = query_params.get('cliente')
        status = query_params.get('status')

        filter_payload = {}
        if cpf:
            filter_payload['cliente__nu_cpf'] = cpf
        if numero_contrato:
            filter_payload['id'] = numero_contrato
        if nome_cliente:
            filter_payload['cliente__nome_cliente__icontains'] = nome_cliente
        if status:
            filter_payload['status'] = status
        return filter_payload

    def post(self, request):
        try:
            # get user
            user = UserProfile.objects.get(
                unique_id=request.data['identificador_usuario']
            )

            # filter user viewable contracts
            query_set = get_viewable_contracts(user)
            query_set = query_set.filter(
                **self.get_contract_filters(
                    request.data,
                )
            )
            total = len(query_set)

            # paginate response
            page_number, items_per_page = get_pagination_data(request, total=total)
            query_set = paginate(query_set, page_number, items_per_page)

            # serialize data
            serializer = api_contrato.ContratoSerializer(
                query_set, many=True, context={'request': request}
            )

            # structure response
            response_data = {'length': total, 'contracts': serializer.data}

            # returns
            return Response(response_data)

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


class DetalheContrato(GenericAPIView):
    def post(self, request):
        try:
            if token_contrato := request.data['token_contrato']:
                contrato = Contrato.objects.get(token_contrato=token_contrato)
                valid_types = [
                    EnumTipoAnexo.CONTRACHEQUE,
                    EnumTipoAnexo.DOCUMENTOS_ADICIONAIS,
                    EnumTipoAnexo.DOCUMENTO_FRENTE,
                    EnumTipoAnexo.DOCUMENTO_VERSO,
                    EnumTipoAnexo.CNH,
                    EnumTipoAnexo.COMPROVANTE_ENDERECO,
                    EnumTipoAnexo.SELFIE,
                ]

                if (
                    contrato.cliente
                    and contrato.cliente.escolaridade == EnumEscolaridade.ANALFABETO
                ):
                    valid_types += [EnumTipoAnexo.TERMOS_E_ASSINATURAS]

                anexos = AnexoContrato.objects.filter(
                    contrato=contrato, tipo_anexo__in=valid_types
                )
                anexo_field = [
                    {
                        'url': anexo.get_attachment_url,
                        'extensao': anexo.anexo_extensao,
                        'tipo': anexo.tipo_anexo,
                        'ativo': anexo.active,
                        'anexo_id': anexo.id,
                    }
                    for anexo in anexos
                ]

                serializer = api_contrato.DetalheContratoSerializer(
                    contrato, many=False, context={'request': request}
                )
                serializer_data_copy = (
                    serializer.data.copy()
                )  # Cria uma cópia do objeto serializer.data
                serializer_data_copy['anexos'] = (
                    anexo_field  # Adiciona os anexos à cópia
                )
                status = StatusContrato.objects.filter(contrato=contrato)
                status_serializer = StatusContratoSerializer(status, many=True)
                serializer_data_copy['status'] = status_serializer.data
                serializer_data_copy['status_macro'] = contrato.status
                cliente = Cliente.objects.filter(contrato=contrato).first()
                if in100_dados := DadosIn100.objects.filter(
                    numero_beneficio=contrato.numero_beneficio
                ).first():
                    in100_data = IN100Serializer(in100_dados).data
                    serializer_data_copy['dados_in100'] = in100_data

                campos_pendentes = {}
                if 'rg' in contrato.campos_pendentes:
                    campos_pendentes['rg'] = cliente.documento_numero
                if 'dt_expedicao_rg' in contrato.campos_pendentes:
                    campos_pendentes['dt_expedicao_rg'] = cliente.documento_data_emissao
                if 'dt_nascimento' in contrato.campos_pendentes:
                    campos_pendentes['dt_nascimento'] = cliente.dt_nascimento
                if 'nome_cliente' in contrato.campos_pendentes:
                    campos_pendentes['nome_cliente'] = cliente.nome_cliente
                if 'sexo' in contrato.campos_pendentes:
                    campos_pendentes['sexo'] = cliente.sexo

                serializer_data_copy['campos_pendentes'] = campos_pendentes
                return Response(serializer_data_copy)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


class HistoricoTeimosinhaInss(GenericAPIView):
    def post(self, request):
        try:
            req_serializer = StubbornINSSHistoryRequestSerializer(data=request.data)

            if not req_serializer.is_valid():
                return Response(req_serializer.errors, status=HTTP_400_BAD_REQUEST)

            token_contrato = req_serializer.validated_data.get('token_contrato')
            tries = TentativaTeimosinhaINSS.objects.filter(
                contrato__token_contrato=token_contrato
            ).order_by('-solicitada_em')

            total = len(tries)

            page_number, items_per_page = get_pagination_data(request, total=total)
            paginated_tries = paginate(tries, page_number, items_per_page)

            serializer = TentativaTeimosinhaINSSSerializer(paginated_tries, many=True)

            response = {'length': total, 'tries': serializer.data}

            return Response(response, status=HTTP_200_OK)
        except Exception:
            msg = 'Não foi possível obter o histórico da teimosinha INSS.'
            logger_detail_contract.exception(msg)
            return Response({'Erro': msg}, status=HTTP_400_BAD_REQUEST)


class ExcluirDocumento(GenericAPIView):
    def post(self, request):
        try:
            if token_contrato := request.data['token_contrato']:
                contrato = Contrato.objects.get(token_contrato=token_contrato)
                contratos = Contrato.objects.filter(
                    token_envelope=contrato.token_envelope
                )
                tipo_anexo = request.data['tipo_anexo']

                for contrato in contratos:
                    anexos = AnexoContrato.objects.filter(
                        contrato=contrato, tipo_anexo=tipo_anexo
                    )
                    for anexo in anexos:
                        anexo.delete()

                return Response({'Arquivo deletado com sucesso!'}, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível excluir o anexo.'},
                status=HTTP_400_BAD_REQUEST,
            )


class DetalheContratoCallCenter(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        context = {}

        contratos = Contrato.objects.all()

        try:
            numero_cpf = request.data['numero_cpf']

            if not re.match(r'\d{3}\.\d{3}\.\d{3}-\d{2}', numero_cpf):
                numero_cpf = f'{numero_cpf[:3]}.{numero_cpf[3:6]}.{numero_cpf[6:9]}-{numero_cpf[9:]}'

            contratos = contratos.filter(cliente__nu_cpf=numero_cpf)
            serializer = api_contrato.CallCenterContratoSerializer(
                contratos, many=True, context={'request': request}
            )
            context['contratos'] = contratos
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


class DetalheClienteCallCenter(APIView):
    @csrf_exempt
    def post(self, request):
        try:
            numero_cpf = request.data['numero_cpf']

            if not re.match(r'\d{3}\.\d{3}\.\d{3}-\d{2}', numero_cpf):
                numero_cpf = f'{numero_cpf[:3]}.{numero_cpf[3:6]}.{numero_cpf[6:9]}-{numero_cpf[9:]}'

            cliente = Cliente.objects.get(nu_cpf=numero_cpf)
            serializer = api_contrato.CallCenterClienteSerializer(
                cliente, many=False, context={'request': request}
            )
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o cliente.'},
                status=HTTP_400_BAD_REQUEST,
            )


# API para envio de link de formalização
class EnvioLinkFormalizacaoAPIView(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        try:
            token_envelope = request.data['token']
            necessita_assinatura_fisica = request.data.get(
                'necessita_assinatura_fisica'
            )
            user = request.user

            if user.is_anonymous:
                user = UserProfile.objects.get(identifier='00000000098')

            url_formalizacao_curta = link_formalizacao_envelope(token_envelope, user)

            logger.info(f'{token_envelope} - URL formalização criada com sucesso.')

            try:
                fim_digitacao = request.data['fim_digitacao']
                envelope = EnvelopeContratos.objects.get(token_envelope=token_envelope)
                envelope.fim_digitacao = fim_digitacao
                envelope.duracao_digitacao = fim_digitacao - envelope.inicio_digitacao
                envelope.save()

                contrato = (
                    Contrato.objects.select_related('created_by', 'cliente')
                    .filter(token_envelope=token_envelope)
                    .first()
                )
                user = contrato.created_by

                tokens_envelope = Contrato.objects.filter(created_by=user).values_list(
                    'token_envelope', flat=True
                )
                envelopes = EnvelopeContratos.objects.filter(
                    token_envelope__in=tokens_envelope
                )
                user.media_segundos_digitacao = envelopes.aggregate(
                    Avg('duracao_digitacao')
                )['duracao_digitacao__avg']
                user.save()

                logger.info(
                    f'{token_envelope} - Sucesso média de tempo e funcionalidade UNICO.'
                )

            except Exception:
                logger.error(
                    f'{token_envelope} - Erro média de tempo e funcionalidade UNICO.'
                )

                contrato = Contrato.objects.filter(
                    token_envelope=token_envelope
                ).first()

            if contrato.tipo_produto in {
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.INSS,
            }:
                in100 = DadosIn100.objects.filter(
                    numero_beneficio=contrato.numero_beneficio
                ).first()
                status = StatusContrato.objects.filter(contrato=contrato).last()
                if in100 and in100.retornou_IN100:
                    salvando_retorno_IN100_contrato(in100, in100.cd_beneficio_tipo)
                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        refin = Refinanciamento.objects.filter(
                            contrato=contrato
                        ).first()
                        port = Portabilidade.objects.filter(contrato=contrato).first()
                        refin.status = port.status
                        refin.save()
                    especie = EspecieIN100.objects.filter(
                        numero_especie=in100.cd_beneficio_tipo
                    ).exists()
                    if not especie:
                        payload = {
                            'url_formalizacao_curta': '',
                            'motivo_url_indisponivel': 'Especie não cadastrada',
                        }
                    elif in100.situacao_beneficio in [
                        'INELEGÍVEL',
                        'BLOQUEADA',
                        'BLOQUEADO',
                    ]:
                        payload = {
                            'url_formalizacao_curta': '',
                            'motivo_url_indisponivel': 'Beneficio Bloqueado ou Cessado',
                        }
                    elif status.nome in [
                        ContractStatus.REPROVADO.value,
                        ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
                        ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
                        ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                    ]:
                        contrato.url_formalizacao = '-'
                        contrato.save()
                        payload = {
                            'url_formalizacao_curta': '',
                            'motivo_url_indisponivel': f'{status.descricao_mesa}',
                        }
                    else:
                        if (
                            contrato.cliente
                            and contrato.cliente.escolaridade
                            == EnumEscolaridade.ANALFABETO
                        ):
                            payload = {
                                **api_contrato.LinkFormalizacaoAnalfabetoSerializer(
                                    instance=contrato
                                ).data,
                                'anexos': [
                                    {
                                        anexo.nome_anexo: anexo.get_attachment_url,
                                    }
                                    for anexo in AnexoContrato.objects.filter(
                                        contrato__token_envelope=token_envelope,
                                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                                    )
                                    if 'assinado' not in anexo.nome_anexo
                                ],
                            }
                        else:
                            payload = {
                                'url_formalizacao_curta': f'{url_formalizacao_curta}',
                            }

                else:
                    payload = {
                        'url_formalizacao_curta': '',
                        'motivo_url_indisponivel': 'Aguardando Retorno da IN 100',
                    }

            else:
                payload = {'url_formalizacao_curta': f'{url_formalizacao_curta}'}

                logger.info(f'{token_envelope} - Criação payload URL formalização.')

                if (
                    necessita_assinatura_fisica
                    and contrato.tipo_produto != EnumTipoProduto.SAQUE_COMPLEMENTAR
                ):
                    anexos = AnexoContrato.objects.filter(
                        contrato=contrato,
                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                    )
                    anexos_list = [
                        {
                            anexo.nome_anexo: anexo.get_attachment_url,
                        }
                        for anexo in anexos
                        if (
                            'assinado' not in anexo.nome_anexo
                            and 'REGULAMENTO' not in anexo.nome_anexo
                        )
                    ]
                    payload['anexos'] = anexos_list
            return Response(payload, status=HTTP_200_OK)

        except Exception as e:
            print(e)
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi possível gerar a URL de Formalização.'},
                status=HTTP_400_BAD_REQUEST,
            )


# API para envio de link de formalização
class ModificaFluxoPortabilidadeAPIView(GenericAPIView):
    def post(self, request):
        token_envelope = request.data['token']
        tipo = request.data['tipo']
        try:
            if tipo == 'Modificacao':
                value = request.data['value']
                retorno_qitech = modifica_proposta_portabilidade_financeira_hub(
                    token_envelope, value
                )
            elif tipo == 'Submissao':
                status = request.data['status']
                retorno_qitech = SubmitFinancialPortabilityProposal(
                    contract=token_envelope, status=status
                ).execute()

            payload = {'retorno_qitech': f'{retorno_qitech}'}

            return Response(payload, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


def finalizar_formalizacao(token_envelope, user):
    try:
        contratos = Contrato.objects.filter(token_envelope=token_envelope)
        contratos_com_erro = []
        erro_global = False
        for index, contrato in enumerate(contratos):
            erro_reserva = None
            cliente = contrato.cliente
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
                numero_cpf = cliente.nu_cpf
                convenio = Convenios.objects.get(
                    pk=contrato_cartao.convenio.pk,
                )
                validacao_contrato = ValidacaoContrato.objects.filter(contrato=contrato)
                erro = (
                    True  # ALTERAR PARA FALSE CASO SEJA POSSIVEL APROVAÇÃO AUTOMATICA
                )
                if contrato.contrato_digitacao_manual:
                    erro = True  # NUNCA ALTERAR CASO CONTRATO SEJA DE DIGITACAO MANUAL POIS NAO HAVERA APROVACAO AUTOMATICA
                for validacao in validacao_contrato:
                    if not validacao.checked:
                        erro = True

                if erro:
                    erro_global = True
                else:
                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.EM_AVERBACAO,
                        ContractStatus.EM_AVERBACAO.value,
                        user,
                    )
                    cliente_cartao = contrato.cliente_cartao_contrato.get()

                    if convenio.averbadora == NomeAverbadoras.FACIL.value:
                        erro_reserva = realiza_reserva(
                            numero_cpf,
                            convenio.averbadora,
                            cliente_cartao.convenio.pk,
                            contrato,
                        )

                    elif convenio.averbadora == NomeAverbadoras.ZETRASOFT.value:
                        zetra = Zetra(
                            averbadora_number=convenio.averbadora,
                            convenio_code=cliente_cartao.convenio.pk,
                        )
                        erro_reserva = zetra.margin_reserve(
                            cpf=numero_cpf,
                            server_password=contrato_cartao.senha_servidor,
                            verba=contrato_cartao.verba or contrato_cartao.verba_saque,
                            folha=contrato_cartao.folha
                            or contrato_cartao.folha_compra
                            or contrato_cartao.folha_saque,
                            registration_number=cliente_cartao.numero_matricula,
                            qta_parcela=contrato_cartao.qtd_parcela_saque_parcelado,
                            valor_parcela=contrato_cartao.valor_parcela,
                            customer_benefit_card=cliente_cartao,
                        )

                    elif convenio.averbadora == NomeAverbadoras.QUANTUM.value:
                        erro_reserva = reservar_margem_quantum(
                            numero_cpf,
                            convenio.averbadora,
                            cliente.margem_atual,
                            cliente_cartao.convenio.pk,
                        )

                    elif convenio.averbadora in (
                        NomeAverbadoras.DATAPREV_BRB.value,
                        NomeAverbadoras.DATAPREV_PINE.value,
                    ):
                        erro_reserva = reserva_margem_inss(
                            numero_cpf,
                            convenio.averbadora,
                            contrato,
                            cliente_cartao.margem_atual,
                        )

                    elif convenio.averbadora == NomeAverbadoras.SERPRO.value:
                        serpro = Serpro()
                        erro_reserva = serpro.margin_reserve(
                            cpf=numero_cpf,
                            registration_number=contrato.cliente.numero_matricula,
                            contract_id=contrato.id,
                            card_limit_value=cliente_cartao.margem_atual,
                        )

                    if settings.ORIGIN_CLIENT == 'BRB':
                        atualizacao_cadastral.apply_async(
                            args=[contrato.cliente.nu_cpf]
                        )

                    if erro_reserva and erro_reserva.descricao:
                        alterar_status(
                            contrato,
                            contrato_cartao,
                            EnumContratoStatus.MESA,
                            ContractStatus.RECUSADA_AVERBACAO.value,
                            user,
                        )
                    else:
                        alterar_status(
                            contrato,
                            contrato_cartao,
                            EnumContratoStatus.PAGO,
                            ContractStatus.APROVADA_AVERBACAO.value,
                            user,
                        )
                        if settings.ORIGIN_CLIENT == 'BRB':
                            workflow = chain(
                                atualizacao_cadastral.s(contrato.cliente.nu_cpf),
                                criar_individuo_dock.s(
                                    numero_cpf, contrato.pk, user, convenio.nome
                                ),
                            )
                            workflow.apply_async()
                        else:
                            criar_individuo_dock.apply_async(
                                args=[
                                    'self',
                                    numero_cpf,
                                    contrato.pk,
                                    user,
                                    convenio.nome,
                                ]
                            )
                if erro_reserva and erro_reserva.descricao:
                    contratos_com_erro.append(index)
            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                validacao_contrato = ValidacaoContrato.objects.filter(contrato=contrato)
                contrato_saque = SaqueComplementar.objects.filter(
                    contrato=contrato
                ).first()
                erro = True
                for validacao in validacao_contrato:
                    if not validacao.checked:
                        erro = True

                if erro:
                    erro_global = True
                else:
                    cliente_cartao = contrato_saque.id_cliente_cartao
                    erro_limite_disponivel = False
                    response = limites_disponibilidades(
                        cliente_cartao.id_cartao_dock, cliente, cliente_cartao.pk
                    )
                    if response['saldoDisponivelSaque'] < float(
                        contrato_saque.valor_saque
                    ):
                        alterar_status(
                            contrato,
                            contrato_saque,
                            EnumContratoStatus.CANCELADO,
                            ContractStatus.SAQUE_CANCELADO_LIMITE_DISPONIVEL_INSUFICIENTE.value,
                            user,
                        )
                        erro_limite_disponivel = True
                    if not erro_limite_disponivel:
                        payment_manager = PaymentManager(
                            contrato, user=user, contrato_saque=contrato_saque
                        )
                        payment_manager.process_payment(cliente)

        if erro_global:
            for contrato in contratos:
                last_status = StatusContrato.objects.filter(contrato=contrato).last()
                # TODO: Remove card paradinha feature flag
                should_go_to_corban_desk = (
                    contrato.corban.mesa_corban
                    and (
                        last_status.nome
                        is not ContractStatus.CHECAGEM_MESA_CORBAN.value
                    )
                    and settings.ENVIRONMENT != EnvironmentEnum.PROD.value
                )
                next_status = (
                    ContractStatus.CHECAGEM_MESA_CORBAN
                    if should_go_to_corban_desk
                    else ContractStatus.CHECAGEM_MESA_FORMALIZACAO
                )

                if contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)

                    if (
                        next_status is not ContractStatus.CHECAGEM_MESA_CORBAN
                        and contrato_cartao.convenio.convenio_inss
                        and contrato.contrato_digitacao_manual
                    ):
                        next_status = ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV

                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.MESA,
                        next_status.value,
                        user,
                    )
                elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
                    alterar_status(
                        contrato,
                        contrato_saque,
                        EnumContratoStatus.MESA,
                        next_status.value,
                        user,
                    )

    except Exception as e:
        print(e)


class CallbackConfia(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload_score = request.body
        confia_str = payload_score.decode('utf-8')
        confia_dict = json.loads(confia_str)
        id_transacao_confia = confia_dict.get('id_transacao_confia')
        status = confia_dict.get('code')
        mensagem = confia_dict.get('message')
        try:
            envelope = EnvelopeContratos.objects.get(
                id_transacao_confia=id_transacao_confia
            )
            contratos = Contrato.objects.filter(token_envelope=envelope.token_envelope)
            erro_restritivo = False
            for contrato in contratos:
                error = True
                if contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    campo_status = CartaoBeneficio.objects.get(contrato=contrato)
                if contrato.tipo_produto in (EnumTipoProduto.PORTABILIDADE,):
                    campo_status = Portabilidade.objects.get(contrato=contrato)
                if contrato.tipo_produto in (EnumTipoProduto.SAQUE_COMPLEMENTAR,):
                    campo_status = SaqueComplementar.objects.get(contrato=contrato)

                if status == 0:
                    error = False
                    validado, _ = ValidacaoContrato.objects.update_or_create(
                        contrato=contrato,
                        mensagem_observacao='Resultado Confia',
                        defaults={
                            'mensagem_observacao': f'{mensagem} PELA CONFIA',
                            'checked': True,
                        },
                    )
                    validado.retorno_hub = 'Analise APROVADA'
                    validado.save()
                    contrato.save()
                    valida_status_score(contrato, campo_status, error, erro_restritivo)
                elif status == 104:
                    error = False
                    validado, _ = ValidacaoContrato.objects.update_or_create(
                        contrato=contrato,
                        mensagem_observacao='Resultado Confia',
                        defaults={
                            'mensagem_observacao': mensagem,
                            'checked': False,
                        },
                    )
                    validado.retorno_hub = 'Analise PENDENTE'
                    validado.save()
                    contrato.save()
                else:
                    validado, _ = ValidacaoContrato.objects.update_or_create(
                        contrato=contrato,
                        mensagem_observacao='Resultado CONFIA',
                        defaults={
                            'mensagem_observacao': mensagem,
                            'checked': False,
                        },
                    )
                    validado.retorno_hub = (
                        'CONTRATO REPROVADO por divergencia na Confia'
                    )
                    validado.save()
                    valida_status_score(contrato, campo_status, error, erro_restritivo)

            return Response(
                {'Sucesso': 'Resultado dos Contratos Validados Com sucesso.'},
                HTTP_200_OK,
            )
        except Exception:
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'}, HTTP_400_BAD_REQUEST
            )


class CallbackUnico(APIView):
    permission_classes = [AllowAny]
    serializer_class = UnicoCallbackSerializer
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        return handle_unico_response(request, *args, **kwargs)


def handle_unico_response(request, *args, **kwargs):
    unico_dict = request.data
    id_processo = unico_dict['data']['id']
    try:
        logger.info({'msg': 'Retorno webhook unico', 'data': unico_dict})
        envelope = EnvelopeContratos.objects.get(id_processo_unico=id_processo)
        logger.info({
            'msg': 'envelope encontrado',
            'token_envelope': envelope.token_envelope,
        })
        contratos = Contrato.objects.filter(token_envelope=envelope.token_envelope)
        status = unico_dict['data']['status']
        for contrato in contratos:
            logger.info({'msg': 'contrato', 'token_envelope': contrato.token_contrato})
            error = True
            erro_restritivo = False
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                campo_status = CartaoBeneficio.objects.get(contrato=contrato)
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                campo_status = Portabilidade.objects.get(contrato=contrato)
            if contrato.tipo_produto in (EnumTipoProduto.MARGEM_LIVRE,):
                campo_status = MargemLivre.objects.get(contrato=contrato)
            if contrato.tipo_produto in (EnumTipoProduto.SAQUE_COMPLEMENTAR,):
                campo_status = SaqueComplementar.objects.get(contrato=contrato)

            if status == 2:
                envelope.status_unico = status
                envelope.save()
                msg = 'Regra Score UNICO'
                validado, _ = ValidacaoContrato.objects.update_or_create(
                    contrato=contrato,
                    mensagem_observacao='Regra Score UNICO',
                    defaults={
                        'mensagem_observacao': msg,
                        'checked': False,
                    },
                )
                validado.retorno_hub = 'SCORE REPROVADO Divergencia na Unico'
                validado.save()
                contrato.save()
            elif status == 3:
                score = unico_dict['data']['score']
                envelope.score_unico = score
                envelope.status_unico = status
                envelope.save()

                score_validation = ScoreValidation(
                    contrato, envelope, status, score, campo_status
                )
                rules, error, erro_restritivo = score_validation.execute()
                if not rules:
                    if 50 <= score <= 100:
                        msg = 'Regra Score UNICO'
                        error = False
                        envelope.erro_unico = False
                        envelope.save()
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': True,
                            },
                        )
                        validado.retorno_hub = (f'SCORE APROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
                    elif -10 <= score <= 49:
                        error = True
                        msg = 'Regra Score UNICO'
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': False,
                            },
                        )
                        validado.retorno_hub = (f'SCORE REPROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
                    elif -90 <= score <= -40:
                        msg = 'Regra Score UNICO'
                        erro_restritivo = True
                        envelope.erro_restritivo_unico = True
                        envelope.save()
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': False,
                            },
                        )
                        validado.retorno_hub = (f'SCORE REPROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
                else:
                    if 50 <= score <= 100:
                        msg = 'Regra Score UNICO'
                        error = False
                        envelope.erro_unico = False
                        envelope.save()
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': True,
                            },
                        )
                        validado.retorno_hub = (f'SCORE APROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
                    elif -10 <= score <= 49:
                        msg = 'Regra Score UNICO'
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': False,
                            },
                        )
                        validado.retorno_hub = (f'SCORE REPROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
                    elif -90 <= score <= -40:
                        msg = 'Regra Score UNICO'
                        erro_restritivo = True
                        envelope.erro_restritivo_unico = True
                        envelope.save()
                        validado, _ = ValidacaoContrato.objects.update_or_create(
                            contrato=contrato,
                            mensagem_observacao='Regra Score UNICO',
                            defaults={
                                'mensagem_observacao': msg,
                                'checked': False,
                            },
                        )
                        validado.retorno_hub = (f'SCORE REPROVADO Valor: {score}',)
                        validado.save()
                        contrato.save()
            if contrato.is_main_proposal and contrato.regras_validadas:
                if (
                    contrato.tipo_produto
                    in [
                        EnumTipoProduto.MARGEM_LIVRE,
                        EnumTipoProduto.PORTABILIDADE,
                        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                    ]
                    or settings.ENVIRONMENT != EnvironmentEnum.PROD.value
                ):
                    analyse_cpf(contrato, campo_status)
                else:
                    valida_status_score(
                        contrato,
                        campo_status,
                        error,
                        erro_restritivo,
                    )
        return Response(
            {'Sucesso': 'Score dos Contratos Validados Com sucesso.'}, HTTP_200_OK
        )
    except Exception:
        return Response(
            {'Erro': 'Não foi possível encontrar o contrato.'}, HTTP_400_BAD_REQUEST
        )


def valida_status_score(contrato, campo_status, error, erro_restritivo):
    if error:
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.SAQUE_COMPLEMENTAR,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            # TODO: Remove card paradinha feature flag
            next_status = (
                ContractStatus.CHECAGEM_MESA_CORBAN
                if contrato.corban.mesa_corban
                and settings.ENVIRONMENT != EnvironmentEnum.PROD.value
                else ContractStatus.CHECAGEM_MESA_FORMALIZACAO
            )

            if ultimo_status.nome != next_status.value:
                contrato.status = EnumContratoStatus.MESA
                if campo_status:
                    campo_status.status = next_status.value
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=next_status.value,
                )
        elif contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            if ultimo_status.nome not in [
                ContractStatus.CHECAGEM_MESA_CORBAN.value,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                ContractStatus.REPROVADO.value,
            ]:
                contrato.status = EnumContratoStatus.MESA
                if contrato.is_main_proposal:
                    if campo_status:
                        campo_status.status = ContractStatus.CHECAGEM_MESA_CORBAN.value
                        campo_status.save()
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.CHECAGEM_MESA_CORBAN.value,
                        descricao_mesa='SCORE da UNICO abaixo do aceito',
                    )
                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        refin = Refinanciamento.objects.filter(
                            contrato=contrato
                        ).first()
                        refin.status = ContractStatus.CHECAGEM_MESA_CORBAN.value
                        refin.save()
    if erro_restritivo:
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.SAQUE_COMPLEMENTAR,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            if ultimo_status.nome != ContractStatus.REPROVADA_FINALIZADA.value:
                contrato.status = EnumContratoStatus.CANCELADO
                if campo_status:
                    campo_status.status = ContractStatus.REPROVADA_FINALIZADA.value
                StatusContrato.objects.create(
                    contrato=contrato, nome=ContractStatus.REPROVADA_FINALIZADA.value
                )
        elif contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            if ultimo_status.nome != ContractStatus.REPROVADA_POLITICA_INTERNA.value:
                contrato.status = EnumContratoStatus.CANCELADO
                if campo_status:
                    campo_status.status = (
                        ContractStatus.REPROVADA_POLITICA_INTERNA.value
                    )
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                    descricao_mesa='Recusada por politíca interna (SF) - Biometria facial',
                )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.filter(contrato=contrato).first()
                    refin.status = ContractStatus.REPROVADA_POLITICA_INTERNA.value
                    refin.save()
    if campo_status:
        campo_status.save()
    contrato.save()

    if contrato.is_main_proposal and not error and not erro_restritivo:
        processor = BPOProcessor(contrato, campo_status)

        if processor.bpo is not None:
            processor.execute()
        else:
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                campo_status.status = ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                campo_status.save()
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value,
                )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.filter(contrato=contrato).first()
                    refin.status = ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                    refin.save()


class RetornoSaqueAPIView(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            print(request.data)
            NumeroProposta = request.data['NumeroProposta']
            NumeroContrato = request.data['NumeroContrato']
            valorTED = request.data['ValorTED']
            Status = request.data['Status']
            Banco = request.data['Banco']
            Agencia = request.data['Agencia']
            Conta = request.data['Conta']
            DVConta = request.data['DVConta']
            CPFCNPJ = request.data['CPFCNPJ']
            Observacao = request.data['Observacao']
            try:
                NumeroContrato = request.data['NumeroContrato']
            except Exception:
                pass
            status = slugify(Status)

            numero_contrato = int(NumeroContrato)
            contrato = Contrato.objects.get(pk=numero_contrato)
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                cartao_beneficio = CartaoBeneficio.objects.filter(
                    contrato=contrato
                ).first()
                RetornoSaque.objects.create(
                    contrato=cartao_beneficio.contrato,
                    NumeroProposta=NumeroProposta,
                    valorTED=valorTED,
                    Status=Status,
                    Banco=Banco,
                    Agencia=Agencia,
                    Conta=Conta,
                    DVConta=DVConta,
                    CPFCNPJ=CPFCNPJ,
                    Observacao=Observacao,
                )
                if (
                    cartao_beneficio.status
                    == ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value
                ):
                    return Response({'msg': 'Inserido com sucesso.'}, HTTP_200_OK)

                if status in ['apr', 'aprovado']:
                    contrato = Contrato.objects.filter(
                        pk=cartao_beneficio.contrato.pk
                    ).first()
                    if cartao_beneficio.saque_parcelado:
                        lancamento_saque_parcelado_fatura(
                            contrato.id, cartao_beneficio.id
                        )  # Chama sem o argumento retry_count
                    else:
                        ajustes_financeiros(
                            contrato.id, cartao_beneficio.id
                        )  # Chama sem o argumento retry_count
                    parametro_backoffice = ParametrosBackoffice.objects.get(
                        tipoProduto=contrato.tipo_produto
                    )
                    if parametro_backoffice.enviar_comissionamento:
                        comissionamento_banksoft(contrato)
                elif status in ['rep', 'pen']:
                    cartao_beneficio.status = (
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
                    )
                    StatusContrato.objects.create(
                        contrato=cartao_beneficio.contrato,
                        nome=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    )

                    alterar_status(
                        contrato,
                        cartao_beneficio,
                        EnumContratoStatus.DIGITACAO,
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    )

                    # Verifique se a reprovação atingiu a terceira vez
                    reprovas = RetornoSaque.objects.filter(
                        contrato=cartao_beneficio.contrato, Status='pen'
                    ).count()

                    if reprovas >= 3:
                        # Se for a terceira reprovação, atualiza o status do contrato para o novo status
                        alterar_status(
                            contrato,
                            cartao_beneficio,
                            EnumContratoStatus.DIGITACAO,
                            ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
                        )

            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                saque_complementar = SaqueComplementar.objects.filter(
                    contrato=contrato
                ).first()
                RetornoSaque.objects.create(
                    contrato=saque_complementar.contrato,
                    NumeroProposta=NumeroProposta,
                    valorTED=valorTED,
                    Status=Status,
                    Banco=Banco,
                    Agencia=Agencia,
                    Conta=Conta,
                    DVConta=DVConta,
                    CPFCNPJ=CPFCNPJ,
                    Observacao=Observacao,
                )
                if (
                    saque_complementar.status
                    == ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value
                ):
                    return Response({'msg': 'Inserido com sucesso.'}, HTTP_200_OK)

                if status in ['apr', 'aprovado']:
                    alterar_status(
                        contrato,
                        saque_complementar,
                        EnumContratoStatus.PAGO,
                        ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                    )
                    parametro_backoffice = ParametrosBackoffice.objects.get(
                        tipoProduto=contrato.tipo_produto
                    )
                    if parametro_backoffice.enviar_comissionamento:
                        comissionamento_banksoft(contrato)
                elif status in ['rep', 'pen']:
                    saque_complementar.status = (
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
                    )
                    StatusContrato.objects.create(
                        contrato=saque_complementar.contrato,
                        nome=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    )

                    alterar_status(
                        contrato,
                        saque_complementar,
                        EnumContratoStatus.DIGITACAO,
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    )

                    # Verifique se a reprovação atingiu a terceira vez
                    reprovas = RetornoSaque.objects.filter(
                        contrato=saque_complementar.contrato, Status='pen'
                    ).count()

                    if reprovas >= 3:
                        # Se for a terceira reprovação, atualiza o status do contrato para o novo status
                        alterar_status(
                            contrato,
                            saque_complementar,
                            EnumContratoStatus.DIGITACAO,
                            ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
                        )

            return Response({'msg': 'Inserido com sucesso.'}, HTTP_200_OK)

        except Exception as e:
            print(e)
            return Response(
                {'msg': 'Não foi possível inserir o retorno.'}, HTTP_400_BAD_REQUEST
            )


class RegularizarPendencia(GenericAPIView):
    def post(self, request):
        try:
            token_contrato = request.data['token_contrato']
            campos = False
            contrato = Contrato.objects.filter(token_contrato=token_contrato).first()
            cliente = contrato.cliente
            fields_mapping = {
                'rg': 'documento_numero',
                'dt_expedicao_rg': 'documento_data_emissao',
                'dt_nascimento': 'dt_nascimento',
                'nome_cliente': 'nome_cliente',
                'sexo': 'sexo',
            }

            campos = any(field in request.data for field in fields_mapping)

            for req_field, client_attr in fields_mapping.items():
                if req_field in request.data:
                    setattr(cliente, client_attr, request.data[req_field])
            cliente.save()

            if token_contrato:
                user = UserProfile.objects.get(identifier=request.user.identifier)
                contrato = Contrato.objects.get(token_contrato=token_contrato)
                contratos = Contrato.objects.filter(
                    token_envelope=contrato.token_envelope
                )
                for contrato in contratos:
                    if campos:
                        contrato.campos_pendentes = ''
                    if not campos:
                        contrato.pendente_documento = False
                        contrato.pendente_endereco = False
                        contrato.contracheque_pendente = False
                        contrato.adicional_pendente = False

                    refin = None

                    if contrato.tipo_produto in (
                        EnumTipoProduto.PORTABILIDADE,
                        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                    ):
                        if (
                            contrato.tipo_produto
                            == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                        ):
                            refin = Refinanciamento.objects.get(contrato=contrato)
                        produto = Portabilidade.objects.get(contrato=contrato)
                    elif contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                        produto = MargemLivre.objects.get(contrato=contrato)
                    elif contrato.tipo_produto in (
                        EnumTipoProduto.CARTAO_BENEFICIO,
                        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                    ):
                        produto = CartaoBeneficio.objects.get(contrato=contrato)
                    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                        produto = SaqueComplementar.objects.get(contrato=contrato)

                    # TODO: Remove card paradinha feature flag
                    if (
                        self.is_card_product(contrato)
                        and settings.ENVIRONMENT == EnvironmentEnum.PROD.value
                    ):
                        produto.status = ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                        produto.save()
                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                            created_by=user,
                        )
                    else:
                        penultimo_status = (
                            StatusContrato.objects.filter(contrato=contrato)
                            .exclude(data_fase_inicial=None)
                            .order_by('-data_fase_inicial')[1:2]
                            .first()
                        )

                        if contrato.is_main_proposal and not self.is_card_product(
                            contrato
                        ):
                            processor = BPOProcessor(contrato, produto)

                            if processor.bpo is not None:
                                produto.status = (
                                    ContractStatus.VALIDACOES_AUTOMATICAS.value
                                )
                                produto.save()

                                StatusContrato.objects.create(
                                    contrato=contrato,
                                    nome=ContractStatus.VALIDACOES_AUTOMATICAS.value,
                                    created_by=user,
                                )

                                contrato.save()

                                processor.execute()

                                return Response(
                                    {
                                        'Documentos recebidos e serão analisados em breve!'
                                    },
                                    status=HTTP_200_OK,
                                )

                            produto.refresh_from_db()

                        next_status = (
                            ContractStatus.CHECAGEM_MESA_FORMALIZACAO
                            if penultimo_status
                            and penultimo_status.nome
                            == ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                            else ContractStatus.CHECAGEM_MESA_CORBAN
                        )

                        produto.status = next_status.value
                        produto.save()

                        if refin:
                            refin.status = next_status.value
                            refin.save()

                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=next_status.value,
                            created_by=user,
                        )

                contrato.save()

                return Response(
                    {'Pendência regularizada com sucesso!'}, status=HTTP_200_OK
                )
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao regularizar a pendência.'},
                status=HTTP_400_BAD_REQUEST,
            )

    def is_card_product(self, contract: Contrato):
        return contract.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
            EnumTipoProduto.SAQUE_COMPLEMENTAR,
        )


class RegularizarPendenciaAverbacao(GenericAPIView):
    def post(self, request):
        try:
            req_serializer = PendingRegistrationRegularizationRequestSerializer(
                data=request.data
            )

            if not req_serializer.is_valid():
                return Response(req_serializer.errors, status=HTTP_400_BAD_REQUEST)

            token_contrato = req_serializer.data.get('token_contrato')
            contrato = Contrato.objects.filter(token_contrato=token_contrato).first()

            if not contrato:
                return Response(
                    {'Erro': 'Contrato não encontrado.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            cartao_beneficio = CartaoBeneficio.objects.filter(contrato=contrato).first()
            if (
                cartao_beneficio.status
                != ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value
            ):
                return Response(
                    {'Erro': 'Este contrato não está com pendência para averbação.'},
                    status=HTTP_409_CONFLICT,
                )

            regularizacao_contrato = RegularizacaoContrato.objects.filter(
                contrato=contrato,
                active=True,
            ).last()

            if not regularizacao_contrato:
                return Response(
                    {'Erro': 'Pendência não encontrada.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            if arquivo := req_serializer.validated_data.get(
                    'arquivo_regularizacao'
            ):
                regularizacao_contrato.arquivo_regularizacao = arquivo

            if mensagem := req_serializer.validated_data.get(
                    'mensagem_regularizacao'
            ):
                regularizacao_contrato.mensagem_regularizacao = mensagem

            regularizacao_contrato.data_regularizacao = datetime.now()
            regularizacao_contrato.nome_regularizacao = request.user
            regularizacao_contrato.active = False
            regularizacao_contrato.save(
                update_fields=[
                    'arquivo_regularizacao',
                    'mensagem_regularizacao',
                    'data_regularizacao',
                    'nome_regularizacao',
                    'active',
                ]
            )

            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.REGULARIZADA_MESA_AVERBACAO.value,
                created_by=request.user,
            )

            cartao_beneficio.status = ContractStatus.REGULARIZADA_MESA_AVERBACAO.value
            cartao_beneficio.save(update_fields=['status'])

            return Response({'Pendência regularizada com sucesso!'}, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao regularizar a pendência.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerificaDocumentacaoProduto(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            cd_produto = request.data['tipo_produto']
            produto = Produtos.objects.get(cd_produto=cd_produto)

            serializer = api_contrato.DocumentoProdutoSerializer(
                produto, many=False, context={'request': request}
            )
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(
                {'msg': 'Não foi possível consultar os documentos do produto.'},
                HTTP_400_BAD_REQUEST,
            )


class TipoProdutoStatusMapping(GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        produto_por_status = {
            EnumTipoProduto.PORTABILIDADE: [
                8,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                41,
                42,
                43,
                44,
            ],
            EnumTipoProduto.MARGEM_LIVRE: [
                8,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                41,
                42,
                43,
                44,
            ],
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO: [
                8,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                41,
                42,
                43,
                44,
                55,
                56,
                19,
                58,
                60,
            ],
            EnumTipoProduto.CARTAO_BENEFICIO: [
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                40,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                59,
            ],
            EnumTipoProduto.CARTAO_CONSIGNADO: [
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                40,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                59,
            ],
            EnumTipoProduto.SAQUE_COMPLEMENTAR: [
                1,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                15,
                16,
                17,
                18,
                19,
                40,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                59,
            ],
            0: [
                1,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                58,
                59,
                60,
            ],
        }
        return Response(produto_por_status)


class ListarEspecie(GenericAPIView):
    """
    API para listar todas as espécies cadastradas no backoffice que possui o tipo_produto especificado
    """

    def post(self, request):
        try:
            tipo_produto = request.data['tipo_produto']
            especie = EspecieIN100.objects.filter(tipo_produto=tipo_produto)

            serializer = api_contrato.DetalheEspecieIN100(
                especie, many=True, context={'request': request}
            )
            return Response(serializer.data)

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar a Especie.'},
                status=HTTP_400_BAD_REQUEST,
            )


class TypistListView(generics.ListAPIView):
    serializer_class = TypistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserProfile.get_subordinates(self.request.user)


class PaymentResubmissionView(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        webhook_data = json.loads(request.body)
        PaymentManager.reprocess_payment_task(webhook_data)
        return JsonResponse(
            {'message': 'Payment reprocessing initiated due to rejection.'}, status=202
        )


class ExportarContratos(GenericAPIView):
    def extract_tipo_produto(self, request: HttpRequest) -> int:
        """
        Extract the field tipo_produto from request.data.

        Args:
            - request: the incoming request.

        Returns:
            - (int): the extract value, defaults to 0
        """
        value = request.data.get('tipo_produto', None)
        return int(value) if value else 0

    def post(self, request):
        data_inicio = request.data.get('data_inicio', None)
        data_final = request.data.get('data_final', None)
        tipo_produto = self.extract_tipo_produto(request)
        tipo_filtro = request.data.get('tipo_filtro', None)
        status = request.data.get('status', None)
        user_ids = request.data.get('user_ids', [])

        # Determinar o nível hierárquico do usuário e obter IDs apropriados
        nivel_hierarquia_usuario = request.user.nivel_hierarquia

        if nivel_hierarquia_usuario in (
            EnumNivelHierarquia.ADMINISTRADOR,
            EnumNivelHierarquia.DONO_LOJA,
            EnumNivelHierarquia.SUPERVISOR,
        ):
            subordinate_ids = get_subordinate_ids_at_all_levels(request.user)
        else:
            subordinate_ids = {request.user.id}

        if user_ids:
            user_ids.extend(subordinate_ids)
            user_ids.append(request.user.id)

        dataset = get_viewable_contracts(request.user)

        if data_inicio:
            data_inicio = make_aware(datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_final:
            data_final = make_aware(
                datetime.strptime(data_final, '%Y-%m-%d') + timedelta(days=1)
            )

        if tipo_filtro == 'geral':
            if user_ids:
                dataset = dataset.filter(
                    created_by__id__in=user_ids, corban=request.user.corban
                )

            if tipo_produto != 0:
                if status != 0:
                    if tipo_produto in (
                        EnumTipoProduto.CARTAO_BENEFICIO,
                        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                    ):
                        dataset = dataset.filter(
                            tipo_produto=tipo_produto,
                            contrato_cartao_beneficio__status=status,
                            criado_em__range=(data_inicio, data_final),
                        ).order_by('criado_em')
                    elif tipo_produto in (EnumTipoProduto.SAQUE_COMPLEMENTAR,):
                        dataset = dataset.filter(
                            tipo_produto=tipo_produto,
                            contrato_saque_complementar__status=status,
                            criado_em__range=(data_inicio, data_final),
                        ).order_by('criado_em')
                    elif tipo_produto == EnumTipoProduto.PORTABILIDADE:
                        dataset = dataset.filter(
                            tipo_produto=tipo_produto,
                            contrato_portabilidade__status=status,
                            criado_em__range=(data_inicio, data_final),
                        ).order_by('criado_em')
                    elif tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                        dataset = dataset.filter(
                            Q(
                                tipo_produto=tipo_produto,
                                criado_em__range=(data_inicio, data_final),
                            )
                            & (
                                Q(contrato_refinanciamento__status=status)
                                | Q(contrato_portabilidade__status=status)
                            )
                        ).order_by('criado_em')
                    elif tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                        dataset = dataset.filter(
                            tipo_produto=tipo_produto,
                            contrato_margem_livre__status=status,
                            criado_em__range=(data_inicio, data_final),
                        ).order_by('criado_em')
                else:
                    dataset = dataset.filter(
                        tipo_produto=tipo_produto,
                        criado_em__range=(data_inicio, data_final),
                    ).order_by('criado_em')

            else:
                dataset = dataset.filter(
                    criado_em__range=(data_inicio, data_final)
                ).order_by('criado_em')
                if status != 0:
                    status_filters = (
                        Q(contrato_cartao_beneficio__status=status)
                        | Q(contrato_saque_complementar__status=status)
                        | Q(contrato_portabilidade__status=status)
                        | Q(contrato_refinanciamento__status=status)
                        | Q(contrato_margem_livre__status=status)
                    )

                    # Aplica o filtro composto à queryset
                    dataset = dataset.filter(status_filters).distinct()

        elif tipo_filtro in ['digitacao', 'finalizacao']:
            if tipo_produto != 0:
                dataset = dataset.filter(tipo_produto__in=tipo_produto)

            if tipo_filtro == 'digitacao':
                if data_inicio:
                    dataset = dataset.filter(criado_em__gte=(data_inicio))
                if data_final:
                    dataset = dataset.filter(criado_em__lt=(data_final))
            if tipo_filtro == 'finalizacao':
                if data_inicio:
                    dataset = dataset.filter(dt_pagamento_contrato__gte=(data_inicio))
                if data_final:
                    dataset = dataset.filter(dt_pagamento_contrato__lt=(data_final))
                portabilidade_status = Q(
                    contrato_portabilidade__status=ContractStatus.INT_FINALIZADO.value
                )
                cartao_status = Q(
                    contrato_cartao_beneficio__status__in=[
                        ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                        ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                    ]
                )
                dataset = dataset.filter(portabilidade_status | cartao_status)
        elif tipo_filtro == 'saldo-retornado':
            if tipo_produto != 0:
                dataset = dataset.filter(tipo_produto__in=tipo_produto)

            if data_inicio:
                dataset = dataset.filter(
                    contrato_portabilidade__dt_recebimento_saldo_devedor__gte=(
                        data_inicio
                    )
                )
            if data_final:
                dataset = dataset.filter(
                    contrato_portabilidade__dt_recebimento_saldo_devedor__lt=(
                        data_final
                    )
                )
            ids_com_saldo_retornado = (
                StatusContrato.objects.filter(nome=ContractStatus.SALDO_RETORNADO.value)
                .values_list('contrato_id', flat=True)
                .distinct()
            )
            dataset_saldo = dataset.filter(id__in=ids_com_saldo_retornado)
            dataset_rejeitado = dataset.filter(
                contrato_portabilidade__status=ContractStatus.REPROVADO.value,
            ).exclude(contrato_portabilidade__motivo_recusa='')
            dataset = dataset_saldo.union(dataset_rejeitado).order_by(
                'ultima_atualizacao'
            )

        if request.user.groups.filter(name='Mesa Corban').exists():
            dataset = mesa_corban_contracts(request.user)
            dataset = dataset.filter(
                criado_em__range=(data_inicio, data_final)
            ).order_by('criado_em')
        if request.user.groups.filter(name='Corban Master').exists():
            dataset = corban_master_contracts(request.user)
            dataset = dataset.filter(
                criado_em__range=(data_inicio, data_final)
            ).order_by('criado_em')

        ContratoResource = contrato_resource_export(isFront=True)
        dataset_export = ContratoResource().export(dataset)
        formato_exportacao = base_formats.XLSX()
        export_data = formato_exportacao.export_data(dataset_export)

        response = HttpResponse(
            export_data, content_type=formato_exportacao.CONTENT_TYPE
        )
        response['Content-Disposition'] = (
            'attachment; filename="relatorio_contratos.xlsx"'
        )
        return response
