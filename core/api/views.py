import io
import logging
import re
import uuid
from datetime import datetime
from typing import Optional, Union
from urllib.parse import urlparse
from contract.constants import EnumStatus

import boto3
import newrelic.agent
import pandas as pd
import paramiko  # instalar
import pytz
import requests
from celery import chain
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect, QueryDict
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.forms import model_to_dict
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import GenericAPIView, ListAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
)
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey
from slugify import slugify

from auditoria.models import LogAlteracaoCadastral, LogAlteracaoCadastralDadosCliente
from contract.constants import (
    EnumContratoStatus,
    EnumTipoAnexo,
    EnumTipoMargem,
    EnumTipoProduto,
    NomeAverbadoras,
    ProductTypeEnum,
    EnumEscolaridade,
)
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    SaqueComplementar,
)
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import Convenios
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.models.taxa import Taxa
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from contract.serializers import (
    AtualizarContratoSerializer,
    ContratoFormalizacaoSerializer,
    DocumentosContratoPortabilidadeSerializer,
    DocumentosContratoSerializer,
)
from contract.services.payment.payment_manager import PaymentManager
from contract.services.persistance.client import create_rogado
from contract.services.persistance.contract import choose_new_main_proposal
from contract.services.registration.client import (
    can_create_client_with_cellphone,
    ValidateClientFormalization,
)
from contract.services.signatures.contract_terms import (
    SignFormalizationTerms,
)
from core.api.serializers import (
    AtualizarClienteIN100Serializer,
    AtualizarClienteOriginacaoSerializer,
    AtualizarClienteSerializer,
    AvailableOffersRequestGetSerializer,
    BancosBrasileirosSerializer,
    ClienteSerializer,
    CriarEnvelopeContratosSerializer,
    FacetecBlobResultSerializer,
    ParametrosProdutoSerializer,
    ParametrosSerializer,
    TaxaSerializer,
    TermosDeUsoSerializer,
    UnicoJWTSerializer,
    UnicoProcessesRequestDataSerializer,
    RogadoSerializer,
)
from core.choices import ESTADO_CIVIL, TIPOS_CONTA, TIPOS_DOCUMENTO, TIPOS_SEXO, UFS
from core.common.enums import EnvironmentEnum
from core.constants import EnumTipoConta
from core.models import BancosBrasileiros, Cliente, ParametrosBackoffice
from core.models.aceite_in100 import AceiteIN100
from core.models.cliente import ClienteCartaoBeneficio, DadosBancarios
from core.models.parametro_produto import ParametrosProduto
from core.models.termos_de_uso import TermosDeUso
from core.serializers import DetalheIN100Serializer
from core.tasks import process_and_upload_file
from core.utils import (
    alterar_status,
    consulta_cliente,
    formatar_cpf,
    generate_short_url,
    processar_pendencia,
)
from custom_auth.anexo_usuario import AnexoUsuario
from custom_auth.models import FeatureToggle, Produtos, UserProfile
from handlers.brb import atualizacao_cadastral
from handlers.ccb import CCB
from handlers.confia import (
    envia_solicitacao_validacao_biometrica,
    enviar_requisicao_criacao_documentos_confia,
    get_facetec_token_session,
    is_feature_active_for_confia,
    is_valid_anexo_for_confia,
)
from handlers.consultas import (
    consulta_regras_hub,
    converter_base64_selfie,
    upload_base64,
)
from handlers.contrato import get_contract_reproved_status
from handlers.converters import get_base64_from_file
from handlers.dock_consultas import limites_disponibilidades
from handlers.dock_formalizacao import (
    criar_individuo_dock,
)
from handlers.facil import realiza_reserva
from handlers.in100_cartao import reserva_margem_inss
from handlers.neoconsig import Neoconsig
from handlers.quantum import reservar_margem_quantum
from handlers.serpro import Serpro
from handlers.tem_saude import cancelamento_cartao, gerar_token_zeus
from handlers.unico import criar_biometria_unico, gerar_assinatura_unico
from handlers.zenvia_sms import zenvia_sms
from handlers.zetra import Zetra
from message_bus.consumers.face_match_handler import (
    handle_face_match_response,
    send_to_web_socket_server,
)
from message_bus.producers.send_face_matching_request import SendFaceMatchingRequest
from core.models import BeneficiosContratado

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)

logger = logging.getLogger('digitacao')


class BuscarCEP(APIView):
    """
    Retorna endereço para um CEP buscado
    """

    permission_classes = [HasAPIKey | IsAuthenticated]

    def get_address_from_cep(self, cep, webservice):
        """Retorna o endereço correspondente ao número de CEP informado.

        Arguments:
            cep {str} -- CEP a ser consultado.
            webservice {str} -- Serviço de CEP a ser utilizado (APICEP ou VIACEP).
        Returns:
            dict -- Dados do endereço do CEP consultado.
        """
        if webservice == 'APICEP':
            return self._buscar_apicep(cep)
        elif webservice == 'VIACEP':
            return self._buscar_viacep(cep)
        else:
            raise ValueError('WebService inválido')

    def _buscar_apicep(self, cep):
        try:
            response = requests.get(
                f'https://cdn.apicep.com/file/apicep/{cep[:5]}-{cep[5:]}.json'
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f'Erro ao buscar CEP no APICEP: {e}')
            return None

    def _buscar_viacep(self, cep):
        try:
            response = requests.get(f'https://viacep.com.br/ws/{cep}/json/')
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f'Erro ao buscar CEP no ViaCEP: {e}')
            return None

    def post(self, request):
        cep = request.data.get('cep')

        if not cep:
            return Response(
                {'Erro': 'CEP não fornecido'}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            address = self.get_address_from_cep(
                cep, webservice='VIACEP'
            ) or self.get_address_from_cep(cep, webservice='APICEP')

            if not address:
                return Response(
                    {'Erro': 'CEP não encontrado'}, status=status.HTTP_404_NOT_FOUND
                )

            return Response(address, status=status.HTTP_200_OK)

        except Exception as e:
            logging.error(f'Erro ao buscar CEP: {e}')
            return Response(
                {'Erro': 'Ocorreu um erro ao buscar o CEP'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TipoContaAPIView(GenericAPIView):
    """
    API que retorna os tipos de conta bancária aceitos
    """

    def get(self, request):
        tipos_conta = [
            {'id': id, 'tipo_conta': tipo_conta.title()}
            for id, tipo_conta in TIPOS_CONTA
            if id
            not in [
                EnumTipoConta.CORRENTE_PESSOA_JURIDICA,
                EnumTipoConta.CARTAO_MAGNETICO,
            ]
        ]
        return Response(tipos_conta)


class BancosBrasileirosAPIView(GenericAPIView):
    """
    API que retorna os bancos permitidos para os produtos
    """

    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        cd_produto = request.data['cd_produto']

        bancos = BancosBrasileiros.objects.filter(produto__cd_produto=cd_produto)
        serializer = BancosBrasileirosSerializer(bancos, many=True)
        return Response(serializer.data)


class EstadoCivilAPIView(GenericAPIView):
    """
    API que retorna os tipos de estado civil
    """

    def get(self, request):
        estados_civil = []
        for estado_civil in ESTADO_CIVIL:
            estado_civil = {'id': estado_civil[0], 'estado_civil': estado_civil[1]}
            estados_civil.append(estado_civil)
        return Response(estados_civil)


class UFSAPIView(GenericAPIView):
    """
    API que retorna os estados brasileiros
    """

    def get(self, request):
        estados = []
        for uf in UFS:
            estado = {'id': uf[0], 'estado': uf[1]}
            estados.append(estado)
        return Response(estados)


class TiposDocumentosAPIView(GenericAPIView):
    """
    API que retorna os tipo de documentos
    """

    def get(self, request):
        tipo_documentos = []
        for tipo in TIPOS_DOCUMENTO:
            documentos = {
                'id': tipo[0],
                'documento': tipo[1],
            }
            tipo_documentos.append(documentos)
        return Response(tipo_documentos)


class ListarSexosAPIView(GenericAPIView):
    """
    API que retorna os tipo de documentos
    """

    def get(self, request):
        tipo_sexos = []
        for sexo in TIPOS_SEXO:
            sexos = {
                'id': sexo[0],
                'sexo': sexo[1],
            }
            tipo_sexos.append(sexos)
        return Response(tipo_sexos)


class DetalheIN100(GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request, cpf, numero_beneficio=None):
        try:
            if cpf:
                cliente = Cliente.objects.get(nu_cpf=cpf)
                in100 = DadosIn100.objects.filter(
                    cliente=cliente, numero_beneficio=numero_beneficio
                ).first()

                aceite_in100 = None
                try:
                    aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf)
                except AceiteIN100.DoesNotExist:
                    pass

                if (
                    not aceite_in100
                    and in100
                    and in100.retornou_IN100
                    and in100.in100_data_autorizacao_
                ):
                    return Response(
                        {'in100_autorizada': True}, status=status.HTTP_200_OK
                    )
                serializer = DetalheIN100Serializer(cliente)
                return Response(serializer.data, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível retornar os detalhes da IN100.'},
                status=HTTP_400_BAD_REQUEST,
            )


class AtualizarProcessoFormalizacao(APIView):
    """API de atualização de processos durante a formalização (selfie único score)"""

    permission_classes = [AllowAny]
    serializer_class = AtualizarContratoSerializer

    def patch(self, request, *args, **kwargs):
        base_64 = request.data.get('anexo_base64')
        token_envelope = request.data.get('token')
        nome_anexo = request.data.get('nome_anexo')
        tipo_anexo = request.data.get('tipo_anexo')
        anexo_extensao = request.data.get('anexo_extensao')
        id_processo_unico = request.data.get('id_processo_unico')

        logger.info({
            'msg': 'id processo unico recuperado',
            'id_processo_unico': id_processo_unico,
        })

        # try:
        contratos = Contrato.objects.filter(token_envelope=token_envelope)
        envelope = EnvelopeContratos.objects.get(token_envelope=token_envelope)
        envelope.id_processo_unico = id_processo_unico
        envelope.save()

        logger.info({
            'msg': 'envelope encontrado',
            'id_processo_unico': id_processo_unico,
        })

        if not contratos.exists():
            logger.error(f'No contracts on envelope {token_envelope}')
            return Response(
                {'msg': 'Contrato não encontrado em nosso sistema.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        nome_pasta = str(token_envelope)

        for contrato in contratos:
            arquivo_convertido = converter_base64_selfie(
                f'{nome_anexo}', base_64, nome_pasta, contrato
            )
            if anexo := AnexoContrato.objects.filter(
                contrato=contrato, nome_anexo=nome_anexo, tipo_anexo=tipo_anexo
            ):
                anexo.update(
                    contrato_id=contrato.id,
                    nome_anexo=nome_anexo,
                    tipo_anexo=tipo_anexo,
                    anexo_extensao=anexo_extensao,
                    anexo_url=arquivo_convertido,
                )
            else:
                anexo.update_or_create(
                    contrato_id=contrato.id,
                    nome_anexo=nome_anexo,
                    tipo_anexo=tipo_anexo,
                    anexo_extensao=anexo_extensao,
                    anexo_url=arquivo_convertido,
                )

            contrato.selfie_enviada = True
            if contrato.selfie_pendente:
                contrato.selfie_pendente = False
                if (
                    not contrato.pendente_documento
                    and not contrato.pendente_endereco
                    and not contrato.selfie_pendente
                ):
                    if contrato.tipo_produto in (
                        EnumTipoProduto.CARTAO_BENEFICIO,
                        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                    ):
                        contrato.status = EnumContratoStatus.MESA

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

                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=next_status.value,
                        )

                        cartao_beneficio = CartaoBeneficio.objects.filter(
                            contrato=contrato
                        ).first()
                        cartao_beneficio.status = next_status.value
                        cartao_beneficio.save(update_fields=['status'])
            contrato.save()
        return Response(
            {'msg': 'Processo do contrato atualizado com sucesso.'},
            status=status.HTTP_200_OK,
        )


class FacetecConfig(APIView):
    """
    API endpoint que lida com as configurações do Facetec.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            public_face_scan_encryption_key = getattr(
                settings, 'FACETEC_PUBLIC_FACE_SCAN_ENCRYPTION_KEY', None
            )
            device_key_identifier = getattr(
                settings, 'FACETEC_DEVICE_KEY_IDENTIFIER', None
            )
            production_key = getattr(settings, 'FACETEC_PRODUCTION_KEY', None)

            if not all([public_face_scan_encryption_key, device_key_identifier]):
                raise ValueError('Uma ou mais chaves de configuração estão faltando.')

            config_data = {
                'public_face_scan_encryption_key': public_face_scan_encryption_key,
                'device_key_identifier': device_key_identifier,
                'production_key': production_key,
            }

            return Response(config_data)

        except ValueError as e:
            return Response(
                {'erro': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FacetecSessionToken(APIView):
    """
    API endpoint para gerar um token de sessão para o Facetec.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            transaction_id = request.data.get('transaction_id')
            if not transaction_id:
                return Response(
                    {'erro': 'transaction_id não fornecido'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            resposta = get_facetec_token_session(transaction_id)
            if 'code' in resposta and resposta.get('code') == 93:
                return Response(
                    {'error': 'Não foi possível recuperar o token de acesso'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            session_token = resposta.get('sessionToken')
            success = resposta.get('success')
            return Response({'session_token': session_token, 'success': success})

        except Exception as e:
            logging.error(f'Erro ao gerar token de sessão: {e}')
            return Response(
                {'erro': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FacetecBlobResult(APIView):
    """
    API endpoint para lidar com os resultados do Facetec.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = FacetecBlobResultSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        validated_data = serializer.validated_data
        auditTrailImage = validated_data.get('auditTrailImage')
        faceScan = validated_data.get('faceScan')
        lowQualityAuditTrailImage = validated_data.get('lowQualityAuditTrailImage')
        sessionId = validated_data.get('sessionId')
        transactionId = validated_data.get('transactionId')

        try:
            resultado = envia_solicitacao_validacao_biometrica(
                faceScan,
                transactionId,
                auditTrailImage,
                lowQualityAuditTrailImage,
                sessionId,
            )
            scan_result_blob = resultado.get('scanResultBlob')
            error = resultado.get('error')
            return Response({
                'error': error,
                'scan_result_blob': scan_result_blob,
            })
        except Exception as e:
            logging.error(f'Erro ao processar os dados: {e}')
            return Response({'error': str(e)}, status=500)


class DetalheFormalizacao(GenericAPIView):
    permission_classes = [HasAPIKey | AllowAny]

    def refuse_no_ccb_contracts(self, envelope: EnvelopeContratos):
        for contrato_errado in envelope.contracts.filter(
            tipo_produto__in=[
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ],
            is_ccb_generated=False,
        ):
            if contrato_errado.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                product = contrato_errado.contrato_portabilidade.first()
            elif contrato_errado.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                product = contrato_errado.contrato_margem_livre.first()
            elif (
                contrato_errado.tipo_produto
                == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
            ):
                product = contrato_errado.contrato_refinanciamento.first()
            alterar_status(
                contrato_errado,
                product,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO.value,
            )
            choose_new_main_proposal(contrato_errado)
            RefuseProposalFinancialPortability(contrato=contrato_errado).execute()

    def get(self, request, token):
        try:
            envelope = EnvelopeContratos.objects.get(token_envelope=token)
            if envelope.is_any_proposal_being_inserted():
                payload = {
                    'not_ready': True,
                    'reason': 'Ainda há contratos sendo processados',
                }
                return Response(payload, status=HTTP_200_OK)

            if is_feature_active_for_confia() and envelope.id_transacao_confia is None:
                contrato = envelope.contracts.first()
                anexos = AnexoContrato.objects.filter(
                    contrato=contrato,
                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                )
                cliente = contrato.cliente
                anexos_assinatura_confia_list = [
                    {anexo.nome_anexo: anexo.anexo_url}
                    for anexo in anexos
                    if is_valid_anexo_for_confia(anexo)
                ]
                transaction_id, message = enviar_requisicao_criacao_documentos_confia(
                    cliente, anexos_assinatura_confia_list, str(token)
                )
                envelope.id_transacao_confia = transaction_id
                envelope.mensagem_confia = message
                envelope.save(update_fields=['id_transacao_confia', 'mensagem_confia'])

            contratos_portabilidade = envelope.contracts.filter(
                tipo_produto__in=[
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                ],
                is_ccb_generated=True,
            ).exclude(status=EnumContratoStatus.CANCELADO)

            contratos_cartao = envelope.contracts.exclude(
                tipo_produto__in=[
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                ]
            )

            contratos = contratos_portabilidade | contratos_cartao
            anexos_por_contrato = {}
            for contrato in contratos:
                anexos_por_contrato[contrato.id] = []
                delta = datetime.now().astimezone(
                    pytz.UTC
                ) - contrato.link_formalizacao_criado_em.astimezone(pytz.UTC)
                # transformação da diferença em horas
                horas_de_criacao_do_link = delta.total_seconds() / 3600
                if not contrato.selfie_pendente:
                    if horas_de_criacao_do_link >= 168:
                        return Response(
                            {'Erro': 'O link de formalização foi expirado.'},
                            status=HTTP_400_BAD_REQUEST,
                        )

                    if contrato.contrato_assinado:
                        return Response(
                            {'Erro': 'Formalização já realizada.'},
                            status=HTTP_400_BAD_REQUEST,
                        )
                    anexos_por_contrato[contrato.id].extend(
                        {
                            'name': attachment.nome_anexo,
                            'extension': attachment.anexo_extensao,
                            'url': attachment.anexo_url,
                        }
                        for attachment in AnexoContrato.objects.filter(
                            contrato=contrato,
                            tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        )
                    )

            serializer = ContratoFormalizacaoSerializer(
                contratos, many=True, context={'request': request}
            )

            for i, contract_data in enumerate(serializer.data):
                contract_id = contract_data['id']
                serializer.data[i]['anexos'] = anexos_por_contrato.get(contract_id, {})
            self.refuse_no_ccb_contracts(envelope=envelope)

            return Response(
                {
                    'id_transacao_confia': envelope.id_transacao_confia,
                    'contratos': serializer.data,
                },
                status=HTTP_200_OK,
            )

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Não foi possível encontrar o envelope.'},
                status=HTTP_400_BAD_REQUEST,
            )


class EnvioDocumentosClienteFormalizacao(GenericAPIView):
    """
    Método utilizado para inserção de anexos (documentos) dos contratos.
    """

    permission_classes = [AllowAny]
    serializer_class = DocumentosContratoSerializer

    def post(self, request):
        copy_payload = QueryDict(mutable=True)
        copy_payload.update(request.data)
        token_envelope = request.data['token_envelope']
        erros = {}
        envelope = self.obter_envelope(token_envelope)
        if not envelope:
            return Response(
                {'Erro': 'Envelope não encontrado na base de dados'},
                status=HTTP_400_BAD_REQUEST,
            )

        contratos = self.obter_contratos_envelope(token_envelope)
        if not contratos:
            return Response({'Erro': 'Envelope Vazio'}, status=HTTP_400_BAD_REQUEST)

        for contrato in contratos:
            if arquivo := copy_payload.get('arquivo'):
                arquivo_base64, content_type = get_base64_from_file(arquivo)
                copy_payload['anexo_base64'] = arquivo_base64
                copy_payload.pop('arquivo')
            else:
                content_type = 'image/jpg'

            if (
                'anexo_base64' in copy_payload
                and copy_payload['anexo_base64'] is not None
            ):
                copy_payload['nome_anexo'] += str(uuid.uuid4())[:8]
                if copy_payload['anexo_base64']:
                    nome_pasta = str(contrato.token_contrato)

                    arquivo_convertido = upload_base64(
                        copy_payload['nome_anexo'],
                        copy_payload['anexo_base64'],
                        nome_pasta,
                        contrato,
                        content_type,
                    )
                    copy_payload['anexo_url'] = arquivo_convertido

            copy_payload['contrato'] = contrato.pk

            serializer = DocumentosContratoSerializer(data=copy_payload)
            if serializer.is_valid():
                serializer_return = serializer.save()
                self.processar_anexos(contrato, copy_payload)
                if not serializer_return:
                    erros['serializer_return'] = (
                        'Ocorreu um erro no retorno do serializer.'
                    )
            else:
                erros['serialize_is_valid'] = 'Serializer não foi valido'
        if erros:
            return Response(
                {'message': f'{erros} '}, status=status.HTTP_400_BAD_REQUEST
            )
        else:
            return Response(
                {'message': 'Documentos Inseridos com sucesso'},
                status=status.HTTP_200_OK,
            )

    def obter_envelope(self, token_envelope):
        try:
            return EnvelopeContratos.objects.filter(
                token_envelope=token_envelope
            ).first()
        except Exception as e:
            print(e)
            return None

    def obter_contratos_envelope(self, token_envelope):
        try:
            return Contrato.objects.filter(token_envelope=token_envelope)
        except Exception as e:
            print(e)
            return None

    def obter_contrato(self, token_contrato):
        try:
            return Contrato.objects.get(token_contrato=token_contrato)
        except Exception as e:
            print(e)
            return None

    def upload_arquivo_s3(self, copy_payload, token_contrato, buket_name_s3):
        # Envio Documentos formalização
        import os

        arquivo = copy_payload['arquivo']
        nome_anexo = copy_payload['nome_anexo']

        nome_arquivo = arquivo.name
        _, extensao = os.path.splitext(nome_arquivo)
        extensao = extensao.lstrip('.')
        if extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            extensao = 'jpg'
        # file_stream = io.BytesIO(arquivo.read())

        s3 = boto3.resource('s3')
        bucket = s3.Bucket(buket_name_s3)

        nome_pasta = str(token_contrato)
        object_key = f'{nome_pasta}/{nome_anexo}.{extensao}'

        content_type = 'application/pdf' if extensao == 'pdf' else 'image/jpg'
        with arquivo.open() as file:
            bucket.upload_fileobj(
                file, object_key, ExtraArgs={'ContentType': content_type}
            )

            url = s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': buket_name_s3, 'Key': object_key},
                ExpiresIn=31536000,
            )

        return url

    def processar_anexos(self, contrato, copy_payload):
        anexos_contrato = AnexoContrato.objects.filter(contrato=contrato)

        tipo_anexo_flags = {
            4: 'selfie_enviada',
            8: 'enviado_documento_pessoal',
            6: 'enviado_comprovante_residencia',
            16: 'contracheque_enviado',
        }

        frente_verso_flags = {2: False, 3: False, 13: False, 14: False}

        for anexo in anexos_contrato:
            tipo_anexo = anexo.tipo_anexo
            if tipo_anexo in tipo_anexo_flags:
                setattr(contrato, tipo_anexo_flags[tipo_anexo], True)
            if tipo_anexo in frente_verso_flags:
                frente_verso_flags[tipo_anexo] = True

        if frente_verso_flags[2] and frente_verso_flags[3]:
            contrato.enviado_documento_pessoal = True

        if frente_verso_flags[13] and frente_verso_flags[14]:
            contrato.enviado_documento_pessoal = True

        tipo_doc = copy_payload['tipo_anexo']
        if tipo_doc == '8' and contrato.pendente_documento:
            contrato.pendente_documento = False
        if tipo_doc == '6' and contrato.pendente_endereco:
            contrato.pendente_endereco = False
        if tipo_doc == '16' and contrato.contracheque_pendente:
            contrato.contracheque_pendente = False

        contrato.save()


class UpdateFaceMatching(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        unique_id = request.data.get('unique_id')
        match = request.data.get('match')
        error = request.data.get('error')
        response = handle_face_match_response({
            'result': match,
            'user_uuid': unique_id,
            'error': error,
        })

        return Response(
            {
                'detail': f'Face matching updated request sent successfully with status {response}'
            },
            status=status.HTTP_200_OK,
        )


class UserFaceMatching(GenericAPIView):
    permission_classes = [AllowAny]

    def get_s3_url(self, url):
        print(url, 'url used to get the bucket')
        parsed_url = urlparse(url)
        return (
            f"s3://{settings.AWS_USER_DOCS_BUCKET_NAME}/{parsed_url.path.lstrip('/')}"
        )

    def send_face_match(self, unique_id, document_resource_path, selfie_url_path):
        event = SendFaceMatchingRequest()
        print(document_resource_path, selfie_url_path)
        event({
            'unique_id': unique_id,
            'document_resource': document_resource_path,
            'image_url': selfie_url_path,
        })

    def post(self, request):
        unique_id = request.data.get('unique_id')

        if not unique_id:
            print('Received a post request without unique_id.')
            return Response(
                {'detail': 'unique_id is required.'}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = UserProfile.objects.get(unique_id=unique_id)
            anexo_usuario = AnexoUsuario.objects.get(usuario=usuario)
            document_resource_path = self.get_s3_url(anexo_usuario.anexo_url)
            selfie_url_path = self.get_s3_url(anexo_usuario.selfie_url)
            if FeatureToggle.is_feature_active(FeatureToggle.FACE_MATCHING):
                self.send_face_match(unique_id, document_resource_path, selfie_url_path)
                return Response(
                    {'detail': 'Face matching request sent successfully.'},
                    status=status.HTTP_200_OK,
                )
            else:
                send_to_web_socket_server(
                    unique_id, {'user_id': unique_id, 'has_matched': True}
                )

                return Response(
                    {'detail': 'Face matching skipped.'}, status=status.HTTP_200_OK
                )

        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found.'}, status=status.HTTP_404_NOT_FOUND
            )
        except AnexoUsuario.DoesNotExist:
            return Response(
                {'detail': 'AnexoUsuario not found.'}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': f'An unexpected error occurred: {str(e)}.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EnvioDocumentosCliente(GenericAPIView):
    """
    Método utilizado para inserção de anexos (documentos) dos contratos.
    """

    permission_classes = [HasAPIKey | IsAuthenticated]
    serializer_class = DocumentosContratoSerializer

    def post(self, request):
        copy_payload = QueryDict(mutable=True)
        copy_payload.update(request.data)
        token_envelope = request.data['token_envelope']
        erros = {}

        envelope = self.obter_envelope(token_envelope)
        if not envelope:
            return Response(
                {'Erro': 'Envelope não encontrado na base de dados'},
                status=HTTP_400_BAD_REQUEST,
            )

        contratos = self.obter_contratos_envelope(token_envelope)
        if not contratos:
            return Response({'Erro': 'Envelope Vazio'}, status=HTTP_400_BAD_REQUEST)

        if copy_payload['anexo_extensao'] not in {'png', 'jpg', 'jpeg', 'pdf'}:
            return Response(
                {'Erro': 'Não trabalhamos com esse tipo de arquivo'},
                status=HTTP_400_BAD_REQUEST,
            )
        # Pega o arquivo como objeto e retira da payload
        if arquivo := copy_payload.get('arquivo'):
            arquivo_base64, content_type = get_base64_from_file(arquivo)
            copy_payload['anexo_base64'] = arquivo_base64
            copy_payload.pop('arquivo')
        else:
            # Esse sempre é imagem!!!
            arquivo_base64 = copy_payload['anexo_base64']
            content_type = 'image/jpg'

        for contrato in contratos:
            if arquivo_base64:
                copy_payload['nome_anexo'] += str(uuid.uuid4())[:8]
                nome_pasta = str(contrato.token_contrato)
                s3_url = upload_base64(
                    copy_payload['nome_anexo'],
                    arquivo_base64,
                    nome_pasta,
                    contrato,
                    content_type,
                )
                copy_payload['anexo_url'] = s3_url

            copy_payload['contrato'] = contrato.pk

            serializer = DocumentosContratoSerializer(data=copy_payload)
            if serializer.is_valid():
                serializer_return = serializer.save()
                self.processar_anexos(contrato, copy_payload)
                if not serializer_return:
                    erros['serializer_return'] = (
                        'Ocorreu um erro no retorno do serializer.'
                    )
            else:
                erros['serialize_is_valid'] = 'Serializer não foi valido'
        if erros:
            return Response(
                {'message': f'{erros} '}, status=status.HTTP_400_BAD_REQUEST
            )
        else:
            return Response(
                {'message': 'Documentos Inseridos com sucesso'},
                status=status.HTTP_200_OK,
            )

    def obter_envelope(self, token_envelope):
        try:
            return EnvelopeContratos.objects.filter(
                token_envelope=token_envelope
            ).first()
        except Exception as e:
            print(e)
            return None

    def obter_contratos_envelope(self, token_envelope):
        try:
            return Contrato.objects.filter(token_envelope=token_envelope)
        except Exception as e:
            print(e)
            return None

    def obter_contrato(self, token_contrato):
        try:
            return Contrato.objects.get(token_contrato=token_contrato)
        except Exception as e:
            print(e)
            return None

    def upload_arquivo_s3(self, copy_payload, token_contrato, buket_name_s3):
        import os

        arquivo = copy_payload['arquivo']
        nome_anexo = copy_payload['nome_anexo']

        nome_arquivo = arquivo.name
        _, extensao = os.path.splitext(nome_arquivo)
        extensao = extensao.lstrip('.')
        if extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            extensao = 'jpg'
        file_stream = io.BytesIO(arquivo.read())

        s3 = boto3.resource('s3')
        bucket = s3.Bucket(buket_name_s3)

        nome_pasta = str(token_contrato)
        object_key = f'{nome_pasta}/{nome_anexo}.{extensao}'

        content_type = 'application/pdf' if extensao == 'pdf' else 'image/jpg'
        bucket.upload_fileobj(
            file_stream, object_key, ExtraArgs={'ContentType': content_type}
        )

        return s3_cliente.generate_presigned_url(
            'get_object',
            Params={'Bucket': buket_name_s3, 'Key': object_key},
            ExpiresIn=31536000,
        )

    def processar_anexos(self, contrato, copy_payload):
        # Apenas atualiza quais documentos foram enviados
        anexos_contrato = AnexoContrato.objects.filter(contrato=contrato)

        tipo_anexo_flags = {
            4: 'selfie_enviada',
            8: 'enviado_documento_pessoal',
            6: 'enviado_comprovante_residencia',
            16: 'contracheque_enviado',
            12: 'adicional_enviado',
        }

        frente_verso_flags = {2: False, 3: False, 13: False, 14: False}

        for anexo in anexos_contrato:
            tipo_anexo = anexo.tipo_anexo
            if tipo_anexo in tipo_anexo_flags:
                setattr(contrato, tipo_anexo_flags[tipo_anexo], True)
            if tipo_anexo in frente_verso_flags:
                frente_verso_flags[tipo_anexo] = True

        if frente_verso_flags[2] and frente_verso_flags[3]:
            contrato.enviado_documento_pessoal = True

        if frente_verso_flags[13] and frente_verso_flags[14]:
            contrato.enviado_documento_pessoal = True

        contrato.save()


class EnvioDocumentosPortabilidadeCliente(GenericAPIView):
    """
    Endpoint para inserção de anexos (documentos) dos contratos.
    """

    serializer_class = DocumentosContratoPortabilidadeSerializer

    def post(self, request, *args, **kwargs):
        token_envelope = request.data.get('token_envelope')
        arquivo = request.data.get('arquivo')
        nome_anexo = request.data.get('nome_anexo')
        tipo_anexo = request.data.get('tipo_anexo')
        anexo_extensao = request.data.get('anexo_extensao')
        anexo_url = request.data.get('anexo_url')

        try:
            contratos = Contrato.objects.filter(token_envelope=token_envelope)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Contrato não encontrado na base de dados'},
                status=HTTP_400_BAD_REQUEST,
            )

        try:
            for contrato in contratos:
                AnexoContrato.objects.create(
                    contrato_id=contrato.id,
                    arquivo=arquivo,
                    nome_anexo=nome_anexo,
                    tipo_anexo=tipo_anexo,
                    anexo_extensao=anexo_extensao,
                    anexo_url=anexo_url,
                )

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Anexo(s) não inserido(s).'}, status=HTTP_400_BAD_REQUEST
            )

        return Response(
            {'message': 'Anexo(s) inserido(s) com sucesso.'},
            status=status.HTTP_201_CREATED,
        )


class ValidarCPFCliente(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        try:
            numero_cpf: str = request.data.get('numero_cpf')

            if numero_cpf is None:
                return Response(
                    {'erro': 'O campo CPF é obrigatório.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cpf_sem_mascara = re.sub('[^0-9]', '', numero_cpf)
            cpf_com_mascara = f'{cpf_sem_mascara[:3]}.{cpf_sem_mascara[3:6]}.{cpf_sem_mascara[6:9]}-{cpf_sem_mascara[9:]}'
            client = Cliente.objects.filter(
                Q(nu_cpf=cpf_sem_mascara) | Q(nu_cpf=cpf_com_mascara)
            ).first()
            existe_cliente = client is not None

            return Response(
                {'existe_cliente': existe_cliente}, status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response({'erro': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'erro': 'Ocorreu um erro inesperado.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CriacaoCliente(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]
    """
    This method is used to create a client during the journey.
    """

    serializer_class = ClienteSerializer

    def create_or_update_client(
        self,
        numero_cpf: str,
        data_nascimento: str,
        numero_telefone: str,
        nome_cliente: Optional[str] = None,
        numero_beneficio: Optional[str] = None,
        escolaridade: Optional[int] = None,
    ) -> Cliente:
        """
        Creates or updates a client with the provided information.

        This function will update the client's details if an associated IN100 record exists and meets
        certain conditions. If no such record exists, it will create a new client.

        Args:
            numero_cpf (str): The client's CPF number.
            data_nascimento (str): The client's new date of birth.
            numero_telefone (str): The client's new cellphone number.
            nome_cliente (Optional[str]): The client's new name, if provided. Default is None.
            escolaridade (Optional[int]): The client's new education level, if provided. Default is None.
            numero_beneficio (Optional[str]): The client's benefit number, if provided. Default is None.

        Returns:
            Cliente: An object representing the created or updated client.
        """
        cliente, created = Cliente.objects.get_or_create(nu_cpf=numero_cpf)
        in100 = DadosIn100.objects.filter(numero_beneficio=numero_beneficio).first()

        # if settings.ENVIRONMENT != 'PROD':
        #     status_aprovados = [
        #         ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
        #         ContractStatus.VALIDACOES_AUTOMATICAS.value,
        #     ]
        #     status_contratos_existentes = StatusContrato.objects.select_related(
        #         'contrato__cliente'
        #     ).filter(contrato__cliente=cliente, nome__in=status_aprovados)
        #
        #     if status_contratos_existentes.exists():
        #         return cliente

        if data_nascimento:
            data_nascimento = datetime.strptime(data_nascimento, '%d/%m/%Y').date()
            cliente.dt_nascimento = data_nascimento
        cliente.save(update_fields=['dt_nascimento'])

        if settings.ORIGIN_CLIENT == 'DIGIMAIS' or created:
            if numero_telefone:
                cliente.telefone_celular = numero_telefone
            # Só atualiza o nome caso a in100 não tenha chegado
            if nome_cliente and not (
                in100 and in100.retornou_IN100 and in100.in100_data_autorizacao_
            ):
                cliente.nome_cliente = nome_cliente
            if escolaridade:
                cliente.escolaridade = escolaridade

            cliente.save(
                update_fields=[
                    'nome_cliente',
                    'telefone_celular',
                    'escolaridade',
                ]
            )

        return cliente

    def handle_portability_or_free_margin(
        self,
        numero_cpf: str,
        data_nascimento: str,
        numero_telefone: str,
        nome_cliente: str,
        numero_beneficio: str,
        escolaridade: int,
        rogado: dict,
    ) -> Response:
        """
        Handle client creation for Portability and Free Margin products.
        Args:
            numero_cpf (str): client cpf number
            data_nascimento (str): client birth date
            numero_telefone (str): client phone number
            nome_cliente (str): client full name.
        Returns:
            Response: the Response object to reply the given request.
        """
        if numero_telefone:
            # Update flow
            # Call method in following cases
            # 1- Client exists in database
            # 2 - There's no client active with specified cellphone
            # 3 - There's just 1 client active with specified cellphone
            if Cliente.objects.filter(
                nu_cpf=numero_cpf
            ).exists() or can_create_client_with_cellphone(numero_telefone):
                client = self.create_or_update_client(
                    numero_cpf=numero_cpf,
                    data_nascimento=data_nascimento,
                    numero_telefone=numero_telefone,
                    nome_cliente=nome_cliente,
                    numero_beneficio=numero_beneficio,
                    escolaridade=escolaridade,
                )
                payload = ClienteSerializer(client).data

                if escolaridade == EnumEscolaridade.ANALFABETO:
                    # Caso não exista rogado, tenta criar um para que possa ser serializado no próximo passo.
                    rogado = create_rogado(client=client, rogado_payload=rogado)
                    payload['rogado'] = RogadoSerializer(rogado).data

                return Response(payload, status=HTTP_200_OK)
            else:
                raise DRFValidationError(
                    detail={
                        'Erro': 'O telefone informado está vinculado a outro CPF.',
                        'description': 'Existem mais de dois ou clientes ativos no sistema com este mesmo telefone',
                    },
                    code=status.HTTP_400_BAD_REQUEST,
                )

    @staticmethod
    def validate_status(
        product: Optional[Union[MargemLivre, Portabilidade]] = None,
    ) -> bool:
        """
        Validate the status of a product and return True if it is considered inactive.

        Args:
            product (Optional[Union[MargemLivre, Portabilidade]]): The product model to be checked.

        Returns:
            bool: True if the product is considered inactive, otherwise False.
        """
        return product and product.status in get_contract_reproved_status()

    @transaction.atomic()
    def post(self, request) -> Response:
        """
        Handle POST request for client creation with different product types.
        """
        numero_cpf: str = request.data['nu_cpf']
        data_nascimento: str = request.data['dt_nascimento']
        numero_telefone: str = request.data['numero_telefone']
        tipo_produto: EnumTipoProduto = request.data['tipo_produto']
        nome_cliente: str = request.data['nome_cliente']
        codigo_convenio: int = request.data.get('convenio_id')
        margem: float = request.data.get('margem')
        numero_matricula: int = request.data.get('numero_matricula')
        folha: str = request.data.get('folha')
        tipo_margem: EnumTipoMargem = request.data.get('tipo_margem')
        verba = request.data.get('verba')
        folha_compra = request.data.get('folha_compra')
        verba_compra = request.data.get('verba_compra')
        folha_saque = request.data.get('folha_saque')
        verba_saque = request.data.get('verba_saque')
        margem_compra = request.data.get('margem_compra')
        margem_saque = request.data.get('margem_saque')
        instituidor = request.data.get('instituidor')
        convenio_siape = request.data.get('convenio_siape')
        classificacao_siape = request.data.get('classificacao_siape')
        tipo_vinculo_siape = request.data.get('tipo_vinculo')
        numero_beneficio = request.data.get('numero_beneficio')
        escolaridade = request.data.get('escolaridade')

        rogado = request.data.get('rogado', {})

        try:
            if tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                in100 = DadosIn100.objects.filter(
                    numero_beneficio=numero_beneficio
                ).first()
                if in100 and in100.cliente.nu_cpf != numero_cpf:
                    return Response(
                        {'Erro': 'Número de benefício incorreto para CPF digitado.'},
                        status=HTTP_400_BAD_REQUEST,
                    )
                return self.handle_portability_or_free_margin(
                    numero_cpf=numero_cpf,
                    data_nascimento=data_nascimento,
                    numero_telefone=numero_telefone,
                    nome_cliente=nome_cliente,
                    numero_beneficio=numero_beneficio,
                    escolaridade=escolaridade,
                    rogado=rogado,
                )

            return self.handle_other_products(
                numero_cpf=numero_cpf,
                data_nascimento=data_nascimento,
                numero_telefone=numero_telefone,
                nome_cliente=nome_cliente,
                tipo_produto=tipo_produto,
                codigo_convenio=codigo_convenio,
                margem=margem,
                numero_matricula=numero_matricula,
                folha=folha,
                tipo_margem=tipo_margem,
                verba=verba,
                folha_compra=folha_compra,
                verba_compra=verba_compra,
                folha_saque=folha_saque,
                verba_saque=verba_saque,
                margem_compra=margem_compra,
                margem_saque=margem_saque,
                instituidor=instituidor,
                convenio_siape=convenio_siape,
                classificacao_siape=classificacao_siape,
                tipo_vinculo_siape=tipo_vinculo_siape,
                numero_beneficio=numero_beneficio,
            )
        except DRFValidationError:
            raise
        except ValidationError as error:
            raise DRFValidationError(
                detail={'Erro': error.message}, code=status.HTTP_400_BAD_REQUEST
            ) from error
        except Exception as e:
            newrelic.agent.notice_error()
            logging.exception('Something wrong with post of CriacaoCliente')
            raise DRFValidationError(
                detail={'Erro: ': 'Aconteceu um erro durante o registro do cliente.'},
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    def handle_other_products(
        self,
        numero_cpf: str,
        data_nascimento: str,
        numero_telefone: str,
        nome_cliente: str,
        tipo_produto: EnumTipoProduto,
        codigo_convenio: int,
        margem: Optional[float] = None,
        numero_matricula: Optional[int] = None,
        folha: Optional[str] = None,
        tipo_margem: Optional[EnumTipoMargem] = None,
        verba: Optional[str] = None,
        folha_compra: Optional[str] = None,
        verba_compra: Optional[str] = None,
        folha_saque: Optional[str] = None,
        verba_saque: Optional[str] = None,
        margem_compra: Optional[float] = None,
        margem_saque: Optional[float] = None,
        instituidor: Optional[str] = None,
        convenio_siape: Optional[str] = None,
        classificacao_siape: Optional[str] = None,
        tipo_vinculo_siape: Optional[int] = None,
        numero_beneficio: Optional[str] = None,
    ) -> Response:
        """
        Handle the creation of a client for other product types based on the provided information.

        This method manages the client creation process for various product types. It checks for existing contracts,
        creates or updates client details, and returns relevant information in a response object.

        Args:
            numero_cpf (str): The client's CPF number.
            data_nascimento (str): The client's date of birth.
            numero_telefone (str): The client's phone number.
            nome_cliente (str): The client's name.
            tipo_produto (EnumTipoProduto): The type of product.
            codigo_convenio (int): The convention code.
            margem (Optional[float]): The margin, optional.
            numero_matricula (Optional[int]): The client's enrollment number, optional.
            folha (Optional[str]): The sheet code, optional.
            tipo_margem (Optional[EnumTipoMargem]): The type of margin, optional.
            verba (Optional[str]): The client budget.
            folha_compra (Optional[str]): The sheet code.
            verba_compra (Optional[str]): The client budget.
            folha_saque (Optional[str]): The sheet code.
            verba_saque (Optional[str]): The client budget.
            margem_compra (Optional[float]): The margin, optional.
            margem_saque (Optional[float]): The margin, optional.
            instituidor (Optional[str]): The settlor code.
            convenio_siape (Optional[str]): Description of the bodies that are parameterized in the “Agreement - SIAPE” tab in the parameter of the agreement in question.
            classificacao_siape (Optional[str]): The code and description of the bodies that are parameterized in the “Agreement - SIAPE” tab in the parameter of the agreement in question
            tipo_vinculo_siape (Optional[int]): Indicates if the person is a federal worker or pensioner

        Returns:
            Response: A response object containing client information and a status code.
        """
        cliente = self.create_or_update_client(
            numero_cpf,
            data_nascimento,
            numero_telefone,
            nome_cliente,
            numero_beneficio=numero_beneficio,
        )

        if tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        ):
            for contract in Contrato.objects.filter(cliente=cliente):
                if contract.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    try:
                        contract_card_obj = contract.contrato_cartao_beneficio.get()
                        client_card_obj = contract.cliente_cartao_contrato.get()

                        if (
                            client_card_obj.numero_matricula == numero_matricula
                            and client_card_obj.tipo_produto == tipo_produto
                            and client_card_obj.tipo_margem == tipo_margem
                        ):
                            if contract_card_obj.status not in (
                                ContractStatus.REPROVADA_MESA_CORBAN.value,
                                ContractStatus.REPROVADA_FINALIZADA.value,
                                ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
                                ContractStatus.RECUSADA_AVERBACAO.value,
                                ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
                                ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                                ContractStatus.ERRO_CONSULTA_DATAPREV.value,
                                ContractStatus.REPROVADA_MESA_DE_AVERBECAO.value,
                                ContractStatus.REPROVADO.value,
                            ):
                                raise DRFValidationError(
                                    detail={
                                        'Erro': 'Cliente possui um contrato em andamento para '
                                        'esse produto com a mesma matricula/benefício'
                                    },
                                    code=status.HTTP_400_BAD_REQUEST,
                                )
                    except ClienteCartaoBeneficio.DoesNotExist:
                        # Lógica para lidar com a situação onde client_card_obj não existe
                        continue

            convenio = Convenios.objects.get(pk=codigo_convenio)
            try:
                (
                    cliente_cartao_beneficio,
                    _,
                ) = ClienteCartaoBeneficio.objects.get_or_create(
                    cliente=cliente,
                    tipo_produto=tipo_produto,
                    convenio=convenio,
                    numero_matricula=numero_matricula,
                    margem_atual=margem,
                    folha=folha,
                    verba=verba,
                    tipo_margem=tipo_margem,
                    folha_compra=folha_compra,
                    verba_compra=verba_compra,
                    folha_saque=folha_saque,
                    verba_saque=verba_saque,
                    margem_compra=margem_compra,
                    margem_saque=margem_saque,
                    instituidor=instituidor,
                    convenio_siape=convenio_siape,
                    classificacao_siape=classificacao_siape,
                    tipo_vinculo_siape=tipo_vinculo_siape,
                )
            except ClienteCartaoBeneficio.MultipleObjectsReturned:
                # Obter todos os registros que correspondem aos critérios
                registros = ClienteCartaoBeneficio.objects.filter(
                    cliente=cliente,
                    tipo_produto=tipo_produto,
                    convenio=convenio,
                    numero_matricula=numero_matricula,
                    margem_atual=margem,
                    folha=folha,
                    verba=verba,
                    tipo_margem=tipo_margem,
                    folha_compra=folha_compra,
                    verba_compra=verba_compra,
                    folha_saque=folha_saque,
                    verba_saque=verba_saque,
                    margem_compra=margem_compra,
                    margem_saque=margem_saque,
                    instituidor=instituidor,
                    convenio_siape=convenio_siape,
                    classificacao_siape=classificacao_siape,
                    tipo_vinculo_siape=tipo_vinculo_siape,
                )

                if registros_com_contrato := registros.exclude(contrato__isnull=True):
                    cliente_cartao_beneficio = registros_com_contrato.order_by(
                        '-id'
                    ).first()
                    registros_com_contrato.exclude(
                        id=cliente_cartao_beneficio.id
                    ).delete()

                if registros_sem_contrato := registros.filter(contrato__isnull=True):
                    ultimo_sem_contrato = registros_sem_contrato.order_by('-id').first()
                    registros_sem_contrato.exclude(id=ultimo_sem_contrato.id).delete()

            cliente_cartao_beneficio_id = cliente_cartao_beneficio.id
            serializer = ClienteSerializer(cliente)
            serialized_data = serializer.data
            serialized_data['cliente_cartao_beneficio_id'] = cliente_cartao_beneficio_id
            return Response(serialized_data, status=HTTP_200_OK)

        serializer = ClienteSerializer(cliente)
        return Response(serializer.data, status=HTTP_200_OK)


class AtualizarCliente(UpdateAPIView):
    """
    Método utilizado para a atualização de cliente
    """

    permission_classes = [HasAPIKey | AllowAny]
    serializer_class = AtualizarClienteOriginacaoSerializer

    def patch(self, request, *args, **kwargs):
        payload = request.data
        cliente_id = request.data['cliente_id']
        numero_beneficio = request.data.get('numero_beneficio')
        cliente = Cliente.objects.get(pk=cliente_id)

        if payload.get('endereco_uf'):
            cliente.endereco_uf = payload.get('endereco_uf')
            cliente.save(update_fields=['endereco_uf'])
        try:
            dados_bancarios = request.data.get('dados_bancarios', [])
            origin = request.GET.get('origin')
            if origin and origin.upper() == 'CORRECAO_DADOS':
                for dado_bancario in dados_bancarios:
                    current_instance = self.find_current_account_details(
                        cliente=cliente, pk=dado_bancario.get('id')
                    )
                    account_details, _, defaults = (
                        self.update_or_create_account_details(
                            cliente=cliente, dado_bancario=dado_bancario
                        )
                    )
                    changed_fields = self.identify_changed_fields(
                        current_instance, account_details, defaults
                    )
                    if changed_fields:
                        self.update_account_and_retry_payment(
                            account_details, cliente, changed_fields
                        )

            else:
                for dado_bancario in dados_bancarios:
                    account_details, _, defaults = (
                        self.update_or_create_account_details(
                            cliente=cliente, dado_bancario=dado_bancario
                        )
                    )

        except Exception as e:
            print(e)

        try:
            serializer = AtualizarClienteOriginacaoSerializer(
                cliente, data=payload, partial=True
            )
            if in100 := DadosIn100.objects.filter(
                numero_beneficio=numero_beneficio
            ).exists():
                in100 = DadosIn100.objects.filter(
                    numero_beneficio=numero_beneficio
                ).last()
                if in100.retornou_IN100 and in100.in100_data_autorizacao_:
                    serializer = AtualizarClienteIN100Serializer(
                        cliente, data=payload, partial=True
                    )
            if serializer.is_valid():
                return (
                    Response(
                        {'msg': 'Cliente atualizado com sucesso.'},
                        status=HTTP_200_OK,
                    )
                    if (serializer.save())
                    else Response(
                        {'msg': 'Ocorreu um erro, tente novamente em instantes.'},
                        status=HTTP_400_BAD_REQUEST,
                    )
                )
            erros = serializer.errors
            return Response(erros, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            newrelic.agent.notice_error()
            return Response(
                {'msg': f'Ocorreu um erro, tente novamente em instantes.{e}'},
                status=HTTP_400_BAD_REQUEST,
            )

    def identify_changed_fields(self, instancia_existente, dados_bancarios, defaults):
        campos_alterados = {}
        if instancia_existente:
            for campo, valor_novo in defaults.items():
                valor_original = getattr(instancia_existente, campo, None)
                if valor_original != valor_novo:
                    campos_alterados[campo] = {
                        'original': valor_original,
                        'novo': valor_novo,
                    }
        return campos_alterados

    def update_or_create_account_details(self, cliente, dado_bancario):
        try:
            updated = True

            defaults = {
                'conta_agencia': dado_bancario.get('conta_agencia'),
                'conta_numero': dado_bancario.get('conta_numero'),
                'conta_digito': dado_bancario.get('conta_digito'),
                'conta_cpf_titular': cliente.nu_cpf,
                'conta_tipo_pagamento': 2
                if settings.ORIGIN_CLIENT == 'DIGIMAIS'
                else 1,
            }

            dados_bancarios = (
                DadosBancarios.objects.filter(
                    cliente=cliente,
                    conta_tipo=dado_bancario.get('conta_tipo'),
                    conta_banco=dado_bancario.get('conta_banco'),
                )
                .order_by()
                .last()
            )

            if dados_bancarios:
                dados_bancarios.conta_agencia = dado_bancario.get('conta_agencia')
                dados_bancarios.conta_numero = dado_bancario.get('conta_numero')
                dados_bancarios.conta_digito = dado_bancario.get('conta_digito')
                dados_bancarios.conta_cpf_titular = cliente.nu_cpf
                dados_bancarios.conta_tipo_pagamento = (
                    2 if settings.ORIGIN_CLIENT == 'DIGIMAIS' else 1
                )
                dados_bancarios.save()
            else:
                dados_bancarios = DadosBancarios.objects.create(
                    cliente=cliente,
                    conta_tipo=dado_bancario.get('conta_tipo'),
                    conta_banco=dado_bancario.get('conta_banco'),
                    conta_agencia=dado_bancario.get('conta_agencia'),
                    conta_numero=dado_bancario.get('conta_numero'),
                    conta_digito=dado_bancario.get('conta_digito'),
                    conta_cpf_titular=cliente.nu_cpf,
                    conta_tipo_pagamento=2
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS'
                    else 1,
                )
        except Exception as e:
            logger.error(f'Erro ao atualizar dados bancarios: {e}', exc_info=True)
            updated = False

        return dados_bancarios, updated, defaults

    def find_current_account_details(self, cliente, pk):
        return (
            DadosBancarios.objects.filter(cliente=cliente)
            .order_by('-updated_at')
            .first()
        )

    def _log_changes(self, alteracoes, cliente):
        for field, values in alteracoes.items():
            original_value = values.get('original')
            current_value = values.get('novo')
            log_cadastral, _ = LogAlteracaoCadastral.objects.get_or_create(
                cliente=cliente
            )
            LogAlteracaoCadastralDadosCliente.objects.get_or_create(
                log_cadastral=log_cadastral,
                tipo_registro=field,
                registro_anterior=original_value,
                novo_registro=current_value,
                canal='Canal',
            )

    def update_account_and_retry_payment(self, account_details, client, changes):
        self._log_changes(changes, client)
        contratos = Contrato.objects.filter(cliente=client)
        for contrato in contratos:
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                contrato_saque = CartaoBeneficio.objects.filter(
                    contrato=contrato,
                    status=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                ).first()
                payment_manager = PaymentManager(contrato, benefit_card=contrato_saque)
                if contrato_saque:
                    payment_manager.update_bank_details(
                        account_details,
                        client,
                        proposal_number=contrato_saque.numero_proposta_banksoft,
                    )
            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                contrato_saque = SaqueComplementar.objects.filter(
                    contrato=contrato,
                    status=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                ).first()
                payment_manager = PaymentManager(
                    contrato, contrato_saque=contrato_saque
                )
                if contrato_saque:
                    payment_manager.update_bank_details(
                        account_details,
                        client,
                        proposal_number=contrato_saque.numero_proposta_banksoft,
                    )


class AtualizarClienteCanais(UpdateAPIView):
    """
    Método utilizado para a atualização de cliente utilizado pelos canais
    """

    def patch(self, request, *args, **kwargs):
        payload = request.data
        nu_cpf = payload['nu_cpf']
        cliente = consulta_cliente(nu_cpf)
        if cliente is None:
            return Response(
                {'msg': 'Cliente não encontrado.'},
                status=HTTP_404_NOT_FOUND,
            )
        try:
            if payload.get('endereco_uf') is not None:
                if cliente.endereco_uf is not None and slugify(
                    cliente.endereco_uf
                ) != slugify(payload.get('endereco_uf')):
                    return Response(
                        {
                            'code': 400,
                            'msg': 'Endereço do cliente não atualizado. Mudança de UF não permitida por esse canal. Entre em contato com a Amigoz para mais detalhes de como realizar a mudança.',
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )

            serializer = AtualizarClienteSerializer(
                cliente, data=payload, partial=True, context={'request': request}
            )

            if not serializer.is_valid():
                return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

            return (
                Response({'msg': 'Cliente atualizado com sucesso.'}, status=HTTP_200_OK)
                if (serializer.save())
                else Response(
                    {
                        'msg': 'Ocorreu um erro ao realizar a chamada, contate o suporte.'
                    },
                    status=HTTP_500_INTERNAL_SERVER_ERROR,
                )
            )
        except Exception as e:
            newrelic.agent.notice_error()
            return Response(
                {'msg': f'Ocorreu um erro ao realizar a chamada. {str(e)}'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListarParametros(ListAPIView):
    """
    API da listagem de Parâmetros de Backoffice
    """

    origin = ''

    def get(self, request):
        # Verifica a origem do request
        try:
            origin = request.GET.get('origin').upper()
            if origin == 'FGTS':
                tipo_produto = 1
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'INSS_REPRESENTANTE_LEGAL':
                tipo_produto = 2
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'CARTAO_BENEFICIO_REPRESENTANTE':
                tipo_produto = 3
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'PAB':
                tipo_produto = 4
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'INSS_CORBAN':
                tipo_produto = 5
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'INSS':
                tipo_produto = 6
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'CARTAO_BENEFICIO':
                tipo_produto = 7
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == 'CARTAO_CONSIGNADO':
                tipo_produto = 15
                parameter_list = ParametrosBackoffice.objects.filter(
                    tipoProduto=tipo_produto
                )
            elif origin == '':
                parameter_list = ParametrosBackoffice.objects
            else:
                return Response(
                    {'Erro': 'Não foi possível encontrar o parâmetro backoffice.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            serializer = ParametrosSerializer(
                parameter_list, many=True, context={'request': request}
            )
            return Response(serializer.data)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi possível encontrar o parâmetro backoffice.'},
                status=HTTP_400_BAD_REQUEST,
            )


class CriarCCB(GenericAPIView):
    def post(self, request):
        # id_user = request.user.id
        cpf = request.data['cpf']
        contract_id = request.data.get('id_contrato', None)
        ccb = CCB(cpf, contract_id)
        ret = ccb.cria_ccb('digimais')
        try:
            if ret['message']:
                url_ccb = (ret['url'],)
                return Response(
                    {'message': ret['message'], 'url': url_ccb}, status=ret['status']
                )
        except Exception as e:
            print(e)
        if ret['message']:
            return Response(
                {
                    'message': ret['message'],
                },
                status=ret['status'],
            )


class AssinarCCB(GenericAPIView):
    def post(self, request):
        contract_id = request.data.get('id_contrato', None)
        ccb = CCB(contract_id)
        ret = ccb.assinar_ccb(contract_id=contract_id, documento='digimais')

        try:
            if ret['message']:
                url_ccb = (ret['url'],)
                return Response(
                    {'message': ret['message'], 'url': url_ccb}, status=ret['status']
                )
        except Exception as e:
            print(e)
        if ret['message']:
            return Response({'message': ret['message']}, status=ret['status'])


class ValidarCliente(GenericAPIView):
    permission_classes = [AllowAny]

    def patch(self, request):
        return ValidateClientFormalization(
            token_envelope=request.data['token'],
            cpf=request.data['cpf'],
        ).process_request()


class EnvioSmsCliente(GenericAPIView):
    """
    API para envio do SMS do link de formalização através da zenvia
    """

    def post(self, request):
        token_envelope = request.data['token_envelope']
        numero_telefone = request.data['numero_telefone']
        try:
            contrato = Contrato.objects.filter(token_envelope=token_envelope).first()
            tipo_contrato = contrato.tipo_produto
            parametros_backoffice = ParametrosBackoffice.objects.get(
                tipoProduto=tipo_contrato, ativo=True
            )
            cliente = contrato.cliente
            numero_cpf = cliente.nu_cpf
            token = contrato.token_envelope

            url = parametros_backoffice.url_formalizacao
            url_formalizacao_longa = f'{url}/{token}'

            url_formalizacao_curta = generate_short_url(long_url=url_formalizacao_longa)
            if not url_formalizacao_curta:
                raise DRFValidationError(
                    detail={
                        'Erro': 'Não foi possível gerar a URL curta de formalização.'
                    },
                    code=HTTP_500_INTERNAL_SERVER_ERROR,
                )

            mensagem = (
                parametros_backoffice.texto_sms_formalizacao
                + ' '
                + url_formalizacao_curta
            )
            zenvia_sms(numero_cpf, numero_telefone, mensagem)
            return Response(
                {'msg': f'SMS enviado com sucesso para o numero:+55 {numero_telefone}'},
                status=HTTP_200_OK,
            )

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'SMS não enviado, tente novamente.'},
                status=HTTP_400_BAD_REQUEST,
            )


class ParametroProdutoAPIView(GenericAPIView):
    """
    API dos Parametros de Produtos do Contrato
    """

    def post(self, request):
        try:
            tipo_produto = request.data['tipo_produto']
            parametro_produto = ParametrosProduto.objects.filter(
                tipoProduto=tipo_produto
            ).first()

            serializer = ParametrosProdutoSerializer(parametro_produto)
            print(serializer.data)
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Parametro so produto não encontrado.'},
                status=HTTP_400_BAD_REQUEST,
            )


class ListarTaxasAPIView((ListAPIView)):
    """
    API que retorna as taxas ativas de determinado produto
    """

    def get(self, request):
        tipo_produto = request.GET.get('tipo_produto', EnumTipoProduto.PORTABILIDADE)
        try:
            taxas_ativas = Taxa.objects.filter(
                ativo=True, tipo_produto=tipo_produto
            ).order_by('-taxa')
            serializer = TaxaSerializer(taxas_ativas, many=True)
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Taxa não encontrada.'}, status=HTTP_400_BAD_REQUEST
            )


class CalculoPortabilidade(GenericAPIView):
    """
    API para realizar o cálculo da portabilidade
    """

    def post(self, request):
        try:
            # saldo_devedor = request.data['saldo_devedor']
            # parcelas = request.data['parcelas']
            # prazo = request.data['prazo']
            # taxa = request.data['taxa']

            """Precisamos da forma de como será realizado este cálculo"""
            resultado_calculo = float(400)

            return Response(resultado_calculo, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao realizar o cálculo da portabilidade'},
                status=HTTP_400_BAD_REQUEST,
            )


class AssinaturaTermosFormalizacao(GenericAPIView):
    permission_classes = [HasAPIKey | AllowAny]

    def post(self, request):
        return SignFormalizationTerms(
            token_envelope=request.data['token_envelope'],
            latitude=request.data['latitude'],
            longitude=request.data['longitude'],
            public_ip=request.data['ip_publico'],
        ).execute()


class ValidarTelefone(UpdateAPIView):
    """
    Atualização de telefone e validação
    """

    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        try:
            telefone_celular = request.data['telefone_celular']
            tipo_produto = request.data['tipo_produto']

            parametro = ParametrosBackoffice.objects.filter(
                tipoProduto=tipo_produto, ativo=True
            ).first()

            status_reprovado = [
                ContractStatus.REPROVADA_FINALIZADA.value,
                ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
                ContractStatus.RECUSADA_AVERBACAO.value,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                ContractStatus.REPROVADA_MESA_CORBAN.value,
                ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
                ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
                ContractStatus.REPROVADO.value,
                ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
            ]

            if tipo_produto in [
                EnumTipoProduto.CARTAO_CONSIGNADO,
                EnumTipoProduto.CARTAO_BENEFICIO,
            ]:
                contratos = (
                    CartaoBeneficio.objects.exclude(status__in=status_reprovado)
                    .filter(contrato__cliente__telefone_celular=telefone_celular)
                    .count()
                )

            if tipo_produto == EnumTipoProduto.PORTABILIDADE:
                contratos = (
                    Portabilidade.objects.exclude(status__in=status_reprovado)
                    .filter(contrato__cliente__telefone_celular=telefone_celular)
                    .count()
                )

            if contratos < parametro.celulares_por_contrato:
                return Response(
                    {'msg': 'Telefone disponível para criação de contrato'},
                    status=HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        'Erro': 'Limite de contratos para este telefone atingido. Utilize outro número.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            print(e)
            return Response(
                {'msg': 'Ocorreu um erro ao realizar a chamada, contate o suporte.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CriarEnvelope(GenericAPIView):
    """
    API para criar o Envelope
    """

    def post(self, request):
        try:
            inicio_digitacao = None

            inicio_digitacao = request.data['inicio_digitacao']

            envelope = EnvelopeContratos.objects.create(
                inicio_digitacao=inicio_digitacao
            )
            serializer = CriarEnvelopeContratosSerializer(
                envelope, many=False, context={'request': request}
            )
            return Response(serializer.data, status=HTTP_200_OK)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Houve um erro ao tentar criar o envelope.'},
                status=HTTP_400_BAD_REQUEST,
            )


def aprova_contrato(request):
    """Botão para aprovação do contrato manualmente"""
    id_contrato = request.GET.get('id_contrato')
    contrato = Contrato.objects.get(id=id_contrato)
    try:
        user = UserProfile.objects.get(identifier=request.user.identifier)
        cliente = contrato.cliente
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)

            if (
                contrato.contrato_digitacao_manual
                and cartao_beneficio.status
                in (
                    ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                    ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value,
                )
                and not cartao_beneficio.convenio.convenio_inss
            ):
                alterar_status(
                    contrato,
                    cartao_beneficio,
                    EnumContratoStatus.EM_AVERBACAO,
                    ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
                    user,
                )
                messages.success(
                    request,
                    f'Contrato {id_contrato} - {cliente} aprovado. Staus alterado para Checagem - Mesa de Averbação',
                )
                return HttpResponseRedirect('/admin/contract/contrato/')

            if (
                (
                    not contrato.contrato_digitacao_manual
                    or (
                        cartao_beneficio.convenio.convenio_inss
                        and contrato.contrato_digitacao_manual
                    )
                )
                and cartao_beneficio.status
                in (
                    ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                    ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value,
                )
                and cartao_beneficio.convenio.derivacao_mesa_averbacao
            ):
                alterar_status(
                    contrato,
                    cartao_beneficio,
                    EnumContratoStatus.EM_AVERBACAO,
                    ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
                    user,
                )
                messages.success(
                    request,
                    f'Contrato {id_contrato} - {cliente} aprovado. Staus alterado para Checagem - Mesa de Averbação',
                )
                return HttpResponseRedirect('/admin/contract/contrato/')

            alterar_status(
                contrato,
                cartao_beneficio,
                EnumContratoStatus.EM_AVERBACAO,
                ContractStatus.EM_AVERBACAO.value,
                user,
            )

            convenio = Convenios.objects.get(pk=cartao_beneficio.convenio.pk)
            numero_cpf = cliente.nu_cpf
            cliente_cartao = contrato.cliente_cartao_contrato.get()
            erro_reserva = None

            if (
                not contrato.contrato_digitacao_manual
                or cartao_beneficio.convenio.convenio_inss
            ):
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
                    if cliente_cartao.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
                        erro_reserva = zetra.margin_reserve(
                            cpf=numero_cpf,
                            server_password=cartao_beneficio.senha_servidor,
                            verba=cartao_beneficio.verba_saque,
                            folha=cartao_beneficio.folha_saque,
                            registration_number=cliente_cartao.numero_matricula,
                            qta_parcela=cartao_beneficio.qtd_parcela_saque_parcelado,
                            valor_parcela=cartao_beneficio.valor_parcela or 1,
                            customer_benefit_card=cliente_cartao,
                        )
                    elif cliente_cartao.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
                        erro_reserva = zetra.margin_reserve(
                            cpf=numero_cpf,
                            server_password=cartao_beneficio.senha_servidor,
                            verba=cartao_beneficio.verba_compra,
                            folha=cartao_beneficio.folha_compra,
                            registration_number=cliente_cartao.numero_matricula,
                            qta_parcela=cartao_beneficio.qtd_parcela_saque_parcelado,
                            valor_parcela=cartao_beneficio.valor_parcela or 1,
                            customer_benefit_card=cliente_cartao,
                        )
                    else:
                        erro_reserva = zetra.margin_reserve(
                            cpf=numero_cpf,
                            server_password=cartao_beneficio.senha_servidor,
                            verba=cartao_beneficio.verba,
                            folha=cartao_beneficio.folha,
                            registration_number=cliente_cartao.numero_matricula,
                            qta_parcela=cartao_beneficio.qtd_parcela_saque_parcelado,
                            valor_parcela=cartao_beneficio.valor_parcela or 1,
                            customer_benefit_card=cliente_cartao,
                        )

                elif convenio.averbadora == NomeAverbadoras.QUANTUM.value:
                    erro_reserva = reservar_margem_quantum(
                        numero_cpf,
                        convenio.averbadora,
                        cliente_cartao.margem_atual,
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
                    serpro = Serpro(averbadora=convenio.averbadora)
                    erro_reserva = serpro.margin_reserve(
                        cpf=numero_cpf,
                        registration_number=cliente_cartao.numero_matricula,
                        contract_id=contrato.id,
                        card_limit_value=cliente_cartao.margem_atual,
                        codigo_convenio=convenio.pk,
                    )

                elif convenio.averbadora == NomeAverbadoras.NEOCONSIG.value:
                    neoconsig = Neoconsig(averbadora=convenio.averbadora)
                    erro_reserva = neoconsig.margin_reserve_and_confirmation(
                        cpf=numero_cpf,
                        averbadora=convenio.averbadora,
                        codigo_convenio=convenio.pk,
                        contrato=contrato,
                    )

                if erro_reserva.descricao:
                    alterar_status(
                        contrato,
                        cartao_beneficio,
                        EnumContratoStatus.CANCELADO,
                        ContractStatus.RECUSADA_AVERBACAO.value,
                        user,
                    )
                    messages.error(
                        request,
                        'RESERVA recusada, para mais detalhes veja em LOG - REALIZAR RESERVA',
                    )
                    return HttpResponseRedirect(
                        f'/admin/contract/contrato/{id_contrato}'
                    )
            alterar_status(
                contrato,
                cartao_beneficio,
                EnumContratoStatus.PAGO,
                ContractStatus.APROVADA_AVERBACAO.value,
                user,
            )
            if settings.ORIGIN_CLIENT == 'BRB':
                workflow = chain(
                    atualizacao_cadastral.s(contrato.cliente.nu_cpf),
                    criar_individuo_dock.s(
                        numero_cpf,
                        contrato.pk,
                        request.user.identifier,
                        convenio.nome,
                    ),
                )
                workflow.apply_async()
            else:
                criar_individuo_dock.apply_async(
                    args=[
                        'self',
                        numero_cpf,
                        contrato.pk,
                        request.user.identifier,
                        convenio.nome,
                    ]
                )
            messages.success(request, f'Contrato {id_contrato} - {cliente} APROVADO.')
        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            contrato_saque = SaqueComplementar.objects.filter(contrato=contrato).first()
            cliente_cartao = contrato_saque.id_cliente_cartao
            response = limites_disponibilidades(
                cliente_cartao.id_cartao_dock, cliente, cliente_cartao.pk
            )
            if response['saldoDisponivelSaque'] < float(contrato_saque.valor_saque):
                alterar_status(
                    contrato,
                    contrato_saque,
                    EnumContratoStatus.CANCELADO,
                    ContractStatus.SAQUE_CANCELADO_LIMITE_DISPONIVEL_INSUFICIENTE.value,
                    user,
                )
                messages.error(
                    request, 'Saque Cancelado - Limite disponível Insuficiente.'
                )

                return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')

            payment_manager = PaymentManager(
                contrato, user=user, contrato_saque=contrato_saque
            )
            payment_manager.process_payment(cliente)

    except Exception as e:
        logger.error(f'Erro ao aprovar o contrato {id_contrato}, {e}')
        newrelic.agent.notice_error()
        messages.error(request, 'Ocorreu um erro ao aprovar o contrato.')

    if contrato.contrato_digitacao_manual:
        return HttpResponseRedirect('/admin/contract/contrato/')

    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


def revisar_contrato(request):
    id_contrato = request.GET.get('id_contrato')
    try:
        contrato = Contrato.objects.get(id=id_contrato)
        user = UserProfile.objects.get(identifier=request.user.identifier)
        # cliente = contrato.cliente
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            contrato_seq = CartaoBeneficio.objects.filter(contrato=contrato).first()
        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            contrato_seq = SaqueComplementar.objects.filter(contrato=contrato).first()

        alterar_status(
            contrato,
            contrato_seq,
            EnumContratoStatus.MESA,
            ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
            user,
        )
        contrato.contrato_digitacao_manual_validado = True
        contrato.save()
        messages.success(
            request,
            f'Contrato {id_contrato} - Enviado para revisão da mesa de formalização.',
        )

    except Exception as e:
        print(e)
        messages.error(request, 'Ocorreu um erro ao revisar o contrato.')
    return HttpResponseRedirect('/admin/contract/contrato/')


def pendencia_averbacao(request):
    id_contrato = request.GET.get('id_contrato')
    pendente = request.POST.get('pendente')
    motivo_pendencia = request.POST.get('motivo_pendencia')
    arquivo = request.FILES['anexo']

    try:
        contrato = Contrato.objects.get(id=id_contrato)
        user = UserProfile.objects.get(identifier=request.user.identifier)
        cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)
        cliente = contrato.cliente

        if (
            not contrato.selfie_enviada
            and not AnexoContrato.objects.filter(
                tipo_anexo=EnumTipoAnexo.SELFIE
            ).exists()
        ):
            messages.error(
                request,
                'Não foi possível pendenciar o contrato pois o contrato ainda não foi formalizado.',
            )
            return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')

        if pendente:
            try:
                processar_pendencia(
                    contrato,
                    cartao_beneficio,
                    pendente,
                    motivo_pendencia,
                    arquivo,
                    user,
                )
                messages.success(
                    request, f'Contrato {id_contrato} - {cliente} PENDENCIADO.'
                )
            except Exception as e:
                print(e)
                messages.error(
                    request,
                    f'Ocorreu um erro ao pendenciar o Contrato {id_contrato} - {cliente}',
                )

    except Exception as e:
        print(e)
        messages.error(request, 'Ocorreu um erro ao pendenciar o contrato.')

    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


def pendencia_contrato(request):
    id_contrato = request.GET.get('id_contrato')
    pendente_endereco = request.POST.get('pendente_endereco')
    pendente_documento = request.POST.get('pendente_documento')
    pendente_selfie = request.POST.get('pendente_selfie')
    pendente_contracheque = request.POST.get('pendente_contracheque')
    pendente_adicional = request.POST.get('pendente_adicional')
    observacao = request.POST.get('motivo_pendencia')

    try:
        contrato = Contrato.objects.get(id=id_contrato)
        cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)
        cliente = contrato.cliente

        if (
            not contrato.selfie_enviada
            and not AnexoContrato.objects.filter(
                tipo_anexo=EnumTipoAnexo.SELFIE
            ).exists()
        ):
            messages.error(
                request,
                'Não foi possível pendenciar o contrato pois o contrato ainda não foi formalizado.',
            )
            return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')

        if pendente_endereco == 'True' or pendente_endereco:
            contrato.pendente_endereco = True
        if pendente_documento == 'True' or pendente_documento:
            contrato.pendente_documento = True
        if pendente_contracheque == 'True' or pendente_contracheque:
            contrato.contracheque_pendente = True
        if pendente_adicional == 'True':
            contrato.adicional_pendente = True
        if pendente_selfie == 'True':
            parametros_backoffice = ParametrosBackoffice.objects.get(
                ativo=True, tipoProduto=contrato.tipo_produto
            )
            token = contrato.token_envelope
            url = parametros_backoffice.url_formalizacao
            url_formalizacao_longa = f'{url}/{token}'
            short_url = generate_short_url(long_url=url_formalizacao_longa)
            contrato.url_formalizacao = short_url
            contrato.selfie_pendente = True
            mensagem = f'{cliente.nome_cliente}, sua proposta foi pendenciada e será necessário regularizá-la através do link: {short_url}'
            zenvia_sms(cliente.nu_cpf, cliente.telefone_celular, mensagem)

        status_cartao = ContractStatus.PENDENTE_DOCUMENTACAO.value
        if cartao_beneficio.status == ContractStatus.REGULARIZADA_MESA_AVERBACAO.value:
            status_cartao = ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value

        contrato.status = EnumContratoStatus.MESA
        cartao_beneficio.status = status_cartao
        cartao_beneficio.save()
        contrato.save()
        user = UserProfile.objects.get(identifier=request.user.identifier)
        StatusContrato.objects.create(
            contrato=contrato,
            nome=status_cartao,
            created_by=user,
            descricao_mesa=observacao,
        )

        messages.warning(request, f'Contrato {id_contrato} - {cliente} PENDENCIADO.')
    except Exception as e:
        print(e)
        messages.error(request, 'Ocorreu um erro ao pendenciar o contrato.')
    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


# Funçao criada para realizar as validações no backoffice clicando no botão de validar contrato
def valida_contrato(request):
    id_contrato = request.GET.get('id_contrato')
    try:
        contrato = Contrato.objects.get(id=id_contrato)
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)
            if contrato.pendente_endereco:
                messages.error(
                    request,
                    'Ocorreu um erro ao validar: O documento de endereço ainda está pendente.',
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')
            elif contrato.pendente_documento:
                messages.error(
                    request,
                    'Ocorreu um erro ao validar: O documento pessoal ainda está pendente.',
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')
            # cliente = contrato.cliente
            numero_cpf = contrato.cliente.nu_cpf
            consulta_bureau = consulta_regras_hub(numero_cpf, contrato)
            consulta_regras = consulta_bureau['regras']
            for elemento in consulta_regras:
                descricao = elemento['descricao']
                msg = ''
                regra_aprovada = elemento['regra_aprovada']
                # restritiva = elemento['restritiva']
                validado = ValidacaoContrato.objects.filter(
                    contrato=contrato, mensagem_observacao=descricao
                ).exists()
                # Tratamento para as regras especiais de endereco e OCR
                erro_ocr = False
                erro_endereco = False
                ocr = False
                endereco = False
                if regra_aprovada is not True and regra_aprovada is not False:
                    if 'ocr' in regra_aprovada:
                        ocr = True
                    if 'endereco' in regra_aprovada:
                        endereco = True
                if ocr:
                    regra_ocr = regra_aprovada.get('ocr')
                    for regras_validadas in regra_ocr:
                        if not regras_validadas['aprovada']:
                            msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                            erro_ocr = True
                    regra_aprovada = not erro_ocr
                if endereco:
                    regra_endereco = regra_aprovada.get('endereco')
                    for regras_validadas in regra_endereco:
                        if not regras_validadas['aprovada']:
                            msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                            erro_endereco = True
                    regra_aprovada = not erro_endereco
                if validado:
                    validar_check = ValidacaoContrato.objects.get(
                        contrato=contrato, mensagem_observacao=descricao
                    )

                    validar_check.checked = regra_aprovada
                    validar_check.retorno_hub = msg
                    validar_check.dtCriacao = datetime.now()
                    validar_check.save()
                else:
                    ValidacaoContrato.objects.create(
                        contrato=contrato,
                        mensagem_observacao=descricao,
                        checked=regra_aprovada,
                        retorno_hub=msg,
                    )
            contrato.status = EnumContratoStatus.MESA
            cartao_beneficio.status = ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
            user = UserProfile.objects.get(identifier=request.user.identifier)
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                created_by=user,
            )
            cartao_beneficio.save()
            contrato.save()
            messages.info(request, f'Contrato {id_contrato} VALIDADO.')
        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            if contrato.pendente_endereco:
                messages.error(
                    request,
                    'Ocorreu um erro ao validar: O documento de endereço ainda está pendente.',
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')
            elif contrato.pendente_documento:
                messages.error(
                    request,
                    'Ocorreu um erro ao validar: O documento pessoal ainda está pendente.',
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')
            # cliente = contrato.cliente
            numero_cpf = contrato.cliente.nu_cpf
            consulta_bureau = consulta_regras_hub(numero_cpf, contrato)
            consulta_regras = consulta_bureau['regras']
            for elemento in consulta_regras:
                descricao = elemento['descricao']
                msg = ''
                regra_aprovada = elemento['regra_aprovada']
                # restritiva = elemento['restritiva']
                validado = ValidacaoContrato.objects.filter(
                    contrato=contrato, mensagem_observacao=descricao
                ).exists()
                # Tratamento para as regras especiais de endereco e OCR
                erro_ocr = False
                erro_endereco = False
                ocr = False
                endereco = False
                if regra_aprovada is not True and regra_aprovada is not False:
                    if 'ocr' in regra_aprovada:
                        ocr = True
                    if 'endereco' in regra_aprovada:
                        endereco = True
                if ocr:
                    regra_ocr = regra_aprovada.get('ocr')
                    for regras_validadas in regra_ocr:
                        if not regras_validadas['aprovada']:
                            msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                            erro_ocr = True
                    regra_aprovada = not erro_ocr
                if endereco:
                    regra_endereco = regra_aprovada.get('endereco')
                    for regras_validadas in regra_endereco:
                        if not regras_validadas['aprovada']:
                            msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                            erro_endereco = True
                    regra_aprovada = not erro_endereco
                if validado:
                    validar_check = ValidacaoContrato.objects.get(
                        contrato=contrato, mensagem_observacao=descricao
                    )

                    validar_check.checked = regra_aprovada
                    validar_check.retorno_hub = msg
                    validar_check.dtCriacao = datetime.now()
                    validar_check.save()
                else:
                    ValidacaoContrato.objects.create(
                        contrato=contrato,
                        mensagem_observacao=descricao,
                        checked=regra_aprovada,
                        retorno_hub=msg,
                    )
            contrato.status = EnumContratoStatus.MESA
            user = UserProfile.objects.get(identifier=request.user.identifier)
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                created_by=user,
            )
            contrato.save()
            messages.info(request, f'Contrato {id_contrato} VALIDADO.')
    except Exception as e:
        print(e)
        messages.error(
            request,
            'Ocorreu um erro ao validar o contrato cheque os documento adicionados.',
        )
    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


def recusa_contrato(request):
    id_contrato = request.GET.get('id_contrato')
    observacao = request.POST.get('motivo_recusa')
    contrato = Contrato.objects.get(id=id_contrato)

    return refuse_card_contract(contrato, observacao, request)


def refuse_card_contract(contract, message, request=None):
    if request:
        user = request.user
    else:
        user = UserProfile.objects.get(identifier='00000000099')

    try:
        if contract.tipo_produto in [
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ]:
            sub_contract = CartaoBeneficio.objects.get(contrato=contract)
        elif contract.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            sub_contract = SaqueComplementar.objects.get(contrato=contract)
        customer = contract.cliente

        if sub_contract.status in (
            ContractStatus.REGULARIZADA_MESA_AVERBACAO.value,
            ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value,
            ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
        ):
            alterar_status(
                contract,
                sub_contract,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADA_MESA_DE_AVERBECAO.value,
                user,
                observacao=message,
            )
        elif contract.contrato_digitacao_manual:
            alterar_status(
                contract,
                sub_contract,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
                user,
                observacao=message,
            )
        else:
            alterar_status(
                contract,
                sub_contract,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADA_FINALIZADA.value,
                user,
                observacao=message,
            )

        if request:
            messages.error(request, f'Contrato {contract.id} - {customer} REPROVADO.')

    except Exception:
        if request:
            messages.error(request, 'Ocorreu um erro ao recusar o contrato.')

    if request:
        if contract.contrato_digitacao_manual:
            return HttpResponseRedirect('/admin/contract/contrato/')
        return HttpResponseRedirect(f'/admin/contract/contrato/{contract.id}')


def cancelar_plano_tem_saude(request):
    id_cliente = request.GET.get('id_cliente')
    try:
        cliente = Cliente.objects.get(id=id_cliente)
        cliente.token_usuario_tem_saude = ''
        cliente.cartao_tem_saude = ''
        cliente.save()
        token_tem_saude = gerar_token_zeus()
        cancelamento_cartao(cliente, token_tem_saude)
        messages.success(
            request, f'Plano Tem Saude do cliente{cliente} cancelado com SUCESSO'
        )
    except Exception as e:
        print(e)
        messages.error(request, 'Ocorreu um erro ao cancelar o plano tem saude.')
    return HttpResponseRedirect(f'/admin/core/cliente/{id_cliente}')


class ValidarExigenciaGeolocalizacao(GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            contrato = Contrato.objects.filter(token_envelope=token).first()
            if contrato is None or contrato.tipo_produto is None:
                return Response(
                    {'msg': 'Não foram encontrados dados para esse contrato.'},
                    status=HTTP_204_NO_CONTENT,
                )

            parametros_backoffice = ParametrosBackoffice.objects.filter(
                tipoProduto=contrato.tipo_produto
            ).first()
            # Se não houver nenhum parametro para o produto especificado, mantem como default obrigatorio : True.
            if parametros_backoffice is None:
                return Response(
                    {'msg': 'Geolocalização obrigatória.', 'obrigatorio': 'true'},
                    status=HTTP_200_OK,
                )

            return (
                Response(
                    {
                        'msg': 'Geolocalização não obrigatória.',
                        'obrigatorio': str(
                            parametros_backoffice.geolocalizacao_exigida
                        ).lower(),
                    },
                    status=HTTP_200_OK,
                )
                if parametros_backoffice.geolocalizacao_exigida is False
                else Response(
                    {
                        'msg': 'Geolocalização obrigatória.',
                        'obrigatorio': str(
                            parametros_backoffice.geolocalizacao_exigida
                        ).lower(),
                    },
                    status=HTTP_200_OK,
                )
            )
        except Exception as e:
            return Response(
                {
                    'msg': f'ValidarExigenciaGeolocalizacao - Ocorreu um erro ao tentar dados do banco de dados.{e}'
                },
                status=HTTP_400_BAD_REQUEST,
            )


class JwtUnicoAPIView(GenericAPIView):
    """
    Gerar o token JWT da Unico
    """

    permission_classes = [AllowAny]

    def get(self, request):
        data = {}
        try:
            UNICO_PRIVATE_KEY = open(rf'{settings.UNICO_PRIVATE_KEY_PATH}', 'r').read()
            if access_token := gerar_assinatura_unico(UNICO_PRIVATE_KEY):
                serializer_unico = UnicoJWTSerializer(access_token, many=False)
                return Response(serializer_unico.data, status=(HTTP_200_OK))
            else:
                return Response(
                    {'Erro': 'Não foi possível gerar o token.'},
                    status=HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            print('error: ', e)
            return Response(data, status=(HTTP_500_INTERNAL_SERVER_ERROR))


class ProcessesUnicoAPIView(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UnicoProcessesRequestDataSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        try:
            token_envelope = request.data.pop('token_envelope', None)
            if not token_envelope:
                return Response(
                    {'Erro': 'Não foi possível autenticar no parceiro.'},
                    status=HTTP_502_BAD_GATEWAY,
                )
            envelope = EnvelopeContratos.objects.get(token_envelope=token_envelope)
            selfie_encrypted = request.data.pop('selfie_encrypted', None)
            user = request.data
            UNICO_PRIVATE_KEY = open(rf'{settings.UNICO_PRIVATE_KEY_PATH}', 'r').read()
            if access_token := gerar_assinatura_unico(UNICO_PRIVATE_KEY):
                response = criar_biometria_unico(
                    user, selfie_encrypted, access_token['access_token']
                )
                data = response.json()
                logger.info({'msg': 'Resposta unico processes', 'data': data})
                if response.ok:
                    envelope.id_processo_unico = data['Id']
                    envelope.save(update_fields=['id_processo_unico'])
                    return Response({'id_unico': data['Id']}, status=(HTTP_200_OK))
                unico_error = data['Error']
                return Response(
                    {'Erro': f"[{unico_error['Code']}] - {unico_error['Description']}"},
                    status=(HTTP_400_BAD_REQUEST),
                )
            else:
                return Response(
                    {'Erro': 'Não foi possível autenticar no parceiro.'},
                    status=HTTP_502_BAD_GATEWAY,
                )

        except Exception as e:
            return Response({'Erro': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


class AvailableOffersAPIView(GenericAPIView):
    """
    API que retorna as ofertas disponíveis de cross-selling para um produto/cliente
    """

    def get(self, request):
        req_serializer = AvailableOffersRequestGetSerializer(data=request.GET)

        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=HTTP_400_BAD_REQUEST)

        try:
            product_type = int(req_serializer.data.get('tipo_produto', '0'))
            id_cliente = int(req_serializer.data.get('id_cliente', '0'))
            product_parameter = self.get_product_parameter(product_type)
            products = []

            if self.is_benefit_card_offer_available(
                product_type, request.user, product_parameter
            ):
                offer = self.get_benefit_card_offer(id_cliente)
                if offer:
                    products.append(offer)

            return Response({'produtos': products})
        except Exception:
            return Response(
                {'Erro': 'Não foi possível obter as ofertas disponíveis.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def ensure_list(self, maybe_list: Union[any, list[any]]):
        if isinstance(maybe_list, list):
            return maybe_list
        else:
            return [maybe_list]

    def get_product_parameter(self, product_type: int):
        return ParametrosProduto.objects.filter(tipoProduto=product_type).first()

    def user_can_create_product(self, user: UserProfile, product_type: ProductTypeEnum):
        return user.produtos.filter(tipo_produto=product_type).exists()

    def is_product_type_of(
        self,
        product_type: ProductTypeEnum,
        product_type_list: Union[ProductTypeEnum, list[ProductTypeEnum]],
    ):
        list = self.ensure_list(product_type_list)
        return product_type in list

    def get_benefit_card_product_types(self):
        return [
            ProductTypeEnum.BENEFIT_CARD,
            ProductTypeEnum.BENEFIT_CARD_REPRESENTATIVE,
            ProductTypeEnum.PAYROLL_CARD,
        ]

    def is_benefit_card_product(self, product_type: int):
        return self.is_product_type_of(
            product_type, self.get_benefit_card_product_types()
        )

    def product_allow_benefit_card_offer(self, product_parameter: ParametrosProduto):
        return product_parameter.permite_oferta_cartao_inss

    def customer_benefit_allow_contracting(
        self, inss_covenant: Convenios, in100: DadosIn100
    ):
        customer_benefit = inss_covenant.convenio_especie.filter(
            codigo=in100.cd_beneficio_tipo
        ).first()

        if customer_benefit:
            return customer_benefit.permite_contratacao

        return False

    def covenant_has_product_set(
        self, covenant: Convenios, product: EnumTipoProduto, margin_type: EnumTipoMargem
    ):
        return covenant.produto_convenio.filter(
            produto=product, tipo_margem=margin_type
        ).exists()

    def pick_best_benefit_card_offer(
        self,
        margem_rcc: int,
        margem_rmc: int = 0,
        has_rcc_product: bool = False,
        has_rmc_product: bool = False,
    ):
        if margem_rcc and margem_rcc >= margem_rmc and has_rcc_product:
            return {
                'tipo_produto': EnumTipoProduto.CARTAO_BENEFICIO,
                'margem_atual': margem_rcc,
            }

        if margem_rmc > 0 and has_rmc_product:
            return {
                'tipo_produto': EnumTipoProduto.CARTAO_CONSIGNADO,
                'margem_atual': margem_rmc,
            }

        return None

    def is_benefit_card_offer_available(
        self, product_type: int, user: UserProfile, product_parameter: ParametrosProduto
    ):
        return (
            not self.is_benefit_card_product(product_type)
            and self.user_can_create_product(user, ProductTypeEnum.BENEFIT_CARD)
            and self.product_allow_benefit_card_offer(product_parameter)
        )

    def get_benefit_card_offer(self, id_cliente: int):
        inss_covenant = Convenios.objects.filter(ativo=True, convenio_inss=True).first()

        if inss_covenant:
            in100 = DadosIn100.objects.filter(
                cliente_id=id_cliente, retornou_IN100=True
            ).last()

            if in100:
                if self.customer_benefit_allow_contracting(inss_covenant, in100):
                    margem_rcc = in100.margem_livre_cartao_beneficio or 0
                    margem_rmc = in100.margem_livre_cartao_consignado or 0

                    has_rcc_product = self.covenant_has_product_set(
                        inss_covenant,
                        EnumTipoProduto.CARTAO_BENEFICIO,
                        EnumTipoMargem.MARGEM_UNICA,
                    )
                    has_rmc_product = self.covenant_has_product_set(
                        inss_covenant,
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                        EnumTipoMargem.MARGEM_UNICA,
                    )

                    best_offer = self.pick_best_benefit_card_offer(
                        margem_rcc, margem_rmc, has_rcc_product, has_rmc_product
                    )

                    if best_offer:
                        return {
                            **best_offer,
                            'convenio': inss_covenant.id,
                            'folha': in100.cd_beneficio_tipo,
                            'tipo_margem': EnumTipoMargem.MARGEM_UNICA,
                            'numero_matricula': in100.numero_beneficio,
                            'averbadora': inss_covenant.averbadora,
                            'necessita_assinatura_fisica': inss_covenant.necessita_assinatura_fisica,
                            'idade_minima_assinatura': inss_covenant.idade_minima_assinatura,
                        }

        return None


class LegalDocumentsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TermosDeUso.objects.all()
    serializer_class = TermosDeUsoSerializer


class GetParameters(GenericAPIView):
    def post(self, request):
        try:
            contract_id = request.data['contract_id']
            contrato = Contrato.objects.get(id=contract_id)
            produto = Produtos.objects.get(tipo_produto=int(contrato.tipo_produto))
            if produto.confia:
                return Response({'msg': True}, status=HTTP_200_OK)
            return Response(
                {'msg': 'Confia não esta ativado para este produto!'},
                status=HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response({'msg': f'Erro interno! {e}'}, status=HTTP_400_BAD_REQUEST)


class ListArchiveToFtp(GenericAPIView):
    def post(self, request):
        try:
            operacao_sequencial = request.data['operacao_sequencial']
            # Defina as informações de conexão FTP
            ftp_host = settings.GENREALI_FTP_HOST
            ftp_user = settings.GENREALI_FTP_USER
            ftp_password = settings.GENREALI_FTP_PASSWORD
            ftp_port = int(settings.GENREALI_FTP_PORT)
            remote_directory = f'{settings.GENERALI_FTP_PATH}'.replace(
                'NAME', operacao_sequencial
            )

            # Crie uma instância do objeto FTP e faça a conexão e login

            transport = paramiko.Transport((ftp_host, ftp_port))
            transport.connect(username=ftp_user, password=ftp_password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.chdir(remote_directory)
            arquivos_remotos = sftp.listdir('.')
            logger.info(f'Arquivos no FTP: {arquivos_remotos}')
            return Response({'arquivos': f'{arquivos_remotos}'}, status=HTTP_200_OK)
        except Exception as e:
            return Response({'msg': f'Erro interno! {e}'}, status=HTTP_400_BAD_REQUEST)


class TestCreateArchive(GenericAPIView):
    def post(self, request):
        try:
            return Response({'msg': f'{process_and_upload_file()}'}, status=HTTP_200_OK)
        except Exception as e:
            return Response({'msg': f'Erro interno! {e}'}, status=HTTP_400_BAD_REQUEST)


@csrf_exempt
def import_excel_view(request):
    mapeamento_tipos_produto = {
        'Cartão Benefício - Representante Legal': EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        'Cartão Benefício': EnumTipoProduto.CARTAO_BENEFICIO,
        'Cartao Consignado': EnumTipoProduto.CARTAO_CONSIGNADO,
    }

    mapeamento_tipos_margem = {
        'Margem Compra': EnumTipoMargem.MARGEM_COMPRA,
        'Margem Saque': EnumTipoMargem.MARGEM_SAQUE,
        'Margem Unica': EnumTipoMargem.MARGEM_UNICA,
    }

    if request.method == 'POST':
        excel_file = request.FILES['excel_file']
        # TODO: Change pandas lib to openpyxl or xlrd to read an excel to better performance
        df = pd.read_excel(excel_file)

        for _, row in df.iterrows():
            cpf = formatar_cpf(row['CPF'])

            try:
                cliente = Cliente.objects.get(nu_cpf=cpf)
            except Cliente.DoesNotExist:
                # Se o cliente não existir, pule para o próximo registro
                continue

            # Encontre um convenio existente
            convenio_existente = Convenios.objects.filter(
                cliente_convenio__cliente=cliente
            ).last()
            if convenio_existente is None:
                convenio_existente = Convenios.objects.filter(
                    cliente_convenio__cliente=cliente
                ).first()

            tipo_produto = mapeamento_tipos_produto.get(row['Tipo de Produto'])
            tipo_margem = mapeamento_tipos_margem.get(row['Tipo Margem'])

            ClienteCartaoBeneficio.objects.update_or_create(
                cliente=cliente,
                contrato=Contrato.objects.get(id=row['Contrato']),
                defaults={
                    'tipo_produto': tipo_produto,
                    'tipo_margem': tipo_margem,
                    'convenio': convenio_existente,
                    'margem_atual': row['Margem atual'],
                    'numero_matricula': row['Matricula'],
                    'id_conta_dock': row['ID Conta Dock'],
                    'id_cartao_dock': row['ID do cartão na Dock'],
                    'folha': '999',
                },
            )

        messages.success(
            request, 'Dados do cartão de benefício importados com sucesso.'
        )
    return HttpResponseRedirect('/admin/core/cliente')


class ConsultarSegurosContratado(GenericAPIView):
    permission_classes = [HasAPIKey | AllowAny]

    def is_valid_cpf_format(self, cpf):
        return len(cpf) == 14 and cpf[3] == '.' and cpf[7] == '.' and cpf[11] == '-'

    def format_cpf(self, cpf):
        return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'

    def map_enum_status(self) -> dict:
        return {
            EnumStatus.EMPTY: 'EMPTY',
            EnumStatus.CRIADO_COM_SUCESSO: 'CRIADO_COM_SUCESSO',
            EnumStatus.RECUSADO_ERRO_NECESSITA_DE_ATENCAO: 'RECUSADO_ERRO_NECESSITA_DE_ATENCAO',
            EnumStatus.RECUSADO_PELA_OPERADORA: 'RECUSADO_PELA_OPERADORA',
            EnumStatus.CANCELADO: 'CANCELADO',
        }

    def post(self, request):
        try:
            seguros = []
            if 'cpf_cliente' not in request.data:
                return Response(
                    {'msg': 'O CPF do cliente é obrigatório!'},
                    status=HTTP_400_BAD_REQUEST,
                )

            other_fields = [
                f"'{key}'" for key in request.data.keys() if key != 'cpf_cliente'
            ]
            if other_fields:
                return Response(
                    {'msg': f'Os campos {", ".join(other_fields)} não são permitidos!'},
                    status=HTTP_400_BAD_REQUEST,
                )

            cpf_cliente = request.data['cpf_cliente']
            if not self.is_valid_cpf_format(cpf_cliente):
                cpf_cliente = self.format_cpf(cpf_cliente)
            cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
            for contrato in Contrato.objects.filter(cliente=cliente):
                for seguros_contratado in BeneficiosContratado.objects.filter(
                    contrato_emprestimo=contrato
                ):
                    seguro_dict = model_to_dict(seguros_contratado)
                    seguro_dict['valor_segurado'] = seguro_dict.pop('valor_plano')
                    seguro_dict['valor_pago'] = seguro_dict.pop('premio_bruto')
                    seguro_dict['valor_pago_sem_iof'] = seguro_dict.pop(
                        'premio_liquido'
                    )
                    seguro_dict['status'] = self.map_enum_status().get(
                        seguros_contratado.status
                    )
                    seguros.append(seguro_dict)

            return Response({'Seguros contratados': seguros}, status=HTTP_200_OK)
        except BeneficiosContratado.DoesNotExist:
            return Response(
                {'msg': 'Seguro não encontrado!'}, status=HTTP_404_NOT_FOUND
            )
        except Contrato.DoesNotExist:
            return Response(
                {'msg': 'Contrato não encontrado!'}, status=HTTP_404_NOT_FOUND
            )
        except Cliente.DoesNotExist:
            return Response(
                {'msg': 'Cliente não encontrado ou cpf inválido'},
                status=HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {'msg': f'Erro interno! {e}'}, status=HTTP_500_INTERNAL_SERVER_ERROR
            )
