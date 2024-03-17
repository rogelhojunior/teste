import json
import logging
from datetime import date, datetime, timezone
import os
import tempfile
from decimal import Decimal

import boto3
import newrelic.agent
import openpyxl
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView, ListAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework_api_key.permissions import HasAPIKey
from core.models import BeneficiosContratado
from api_log.models import LogCliente, RealizaSimulacao
from contract.api.serializers import LimitesDisponibilidadesSerializer
from contract.constants import (
    EnumContratoStatus,
    EnumSeguradoras,
    EnumTipoContrato,
    EnumTipoMargem,
    EnumTipoPlano,
    EnumTipoProduto,
    NomeAverbadoras,
)
from contract.models.contratos import CartaoBeneficio, Contrato, SaqueComplementar
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.api.serializers import (
    AtualizarClienteSerializer,
    CartaoBeneficioSerializer,
    ConsultaAceiteIN100Cartao,
    ContratoSaqueSerializer,
    CriarContratoSaqueComplementarSerializer,
    RetornaCartaoExistente,
)
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.averbacao_inss import LogAverbacaoINSS
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    ProdutoConvenio,
    RegrasIdade,
)
from contract.products.cartao_beneficio.models.planos import Planos
from contract.products.cartao_beneficio.serializers import (
    ConsultaConveniosSerializer,
    PlanosSerializer,
    PlanosSerializerSeguradora,
)
from contract.products.cartao_beneficio.Simulacao import Simulacao
from contract.products.cartao_beneficio.validators.arquivo_posicionais import (
    ajustar_posicoes,
    calcular_cf,
    check_plano,
    get_maior_sequencial,
    remove_first_line_starting_with,
    write_cancelamento,
    write_initial_content,
    write_trailer,
    escrever_arrecadacao,
    count_reg,
    identificar_parcela,
    check_data_in_range,
)
from contract.products.cartao_beneficio.utils import HasAPIKeyOrAllowAny
from contract.products.cartao_beneficio.validators.validate_idade import calcular_idade
from contract.services.insurance.insurance_agreement import InsuranceDataAgent
from core.constants import EnumCanalAutorizacaoDigital
from core.models import Cliente, ParametrosBackoffice, InformativoCancelamentoPlano
from core.models.aceite_in100 import AceiteIN100, DadosBeneficioIN100
from core.models.cliente import ClienteCartaoBeneficio
from core.serializers import (
    CancelaReservaQuantumSerializer,
    CancelaReservaSerializer,
    ConsultaMargemQuantumSerializer,
    ConsultaMargemSerializer,
    ConsultaMargemZetraSerializer,
    ConsultaMatriculaFacilSerializer,
    ConsultaMatriculaQuantumSerializer,
    ConsultaMatriculaSerializer,
    RealizaReservaDataprevSerializer,
    RealizaReservaQuantumSerializer,
    RealizaReservaSerializer,
    ConsultaMargemSerproSerializer,
)
from core.utils import (
    consulta_cliente,
    filter_valid_margins,
    gerar_link_aceite_in100,
    is_value_in_enum,
)
from custom_auth.models import UserProfile
from handlers.brb import atualizacao_cadastral
from handlers.dock_constants import StatusAccountDock, StatusCardDock
from handlers.dock_consultas import (
    limites_disponibilidades,
    simulacao_saque_parcelado_dock,
)
from handlers.dock_formalizacao import consulta_cartao_dock, consulta_conta_dock
from handlers.facil import cancela_reserva, consulta_matricula, realiza_reserva
from handlers.in100_cartao import (
    autorizacao_consulta_digital,
    consulta_beneficio,
    consulta_margem_inss,
    incluir_desconto_cartao,
    reserva_margem_inss,
)
from handlers.neoconsig import Neoconsig
from handlers.quantum import (
    cancela_reserva_quantum,
    consulta_consignacoes_quantum,
    consulta_margem_quantum,
    consulta_martricula_quantum,
    reservar_margem_quantum,
)
from handlers.serpro import Serpro
from handlers.simulacao_cartao import (
    calcula_simulacao_iof,
    calcula_simulacao_iof_saque_complementar,
)
from handlers.termos_in100 import aceite_in100, aceite_in100_digimais, aceite_in100_pine
from handlers.zetra import (
    Zetra,
)
from handlers.solicitar_cobranca_dock import solicitar_cobranca_operacoes

logger = logging.getLogger('digitacao')


class ConveniosApiView(ListAPIView):
    """
    API para que retorna todos Parâmetros de Convênios
    """

    permission_classes = [HasAPIKey | IsAuthenticated]

    def get(self, request):
        try:
            convenios = Convenios.objects.filter(ativo=True).order_by('nome')
            serializer = ConsultaConveniosSerializer(convenios, many=True)
            return Response(serializer.data, status=HTTP_200_OK)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi possível consultar os convênios.'},
                status=HTTP_400_BAD_REQUEST,
            )


# API DE CONSULTAR MATRÍCULA NAS AVERBADORAS
@api_view(['POST', 'GET'])
def registration_view(request):
    logger = logging.getLogger('digitacao')

    if request.method == 'POST':
        numero_cpf = request.data.get('numero_cpf')
        averbadora = request.data.get('averbadora')
        codigo_convenio = request.data.get('convenio')

        numero_matricula = request.data.get('numero_matricula')
        senha_servidor = request.data.get('senha_servidor')

        if averbadora == NomeAverbadoras.FACIL.value:
            matricula, erro = consulta_matricula(
                numero_cpf, averbadora, codigo_convenio
            )

        elif averbadora == NomeAverbadoras.ZETRASOFT.value:
            zetra = Zetra(averbadora_number=averbadora, convenio_code=codigo_convenio)
            matricula, erro = zetra.registration_consult(
                cpf=numero_cpf,
                registration_number=numero_matricula,
                server_password=senha_servidor,
            )

        elif averbadora == NomeAverbadoras.QUANTUM.value:
            matricula, erro = consulta_martricula_quantum(
                numero_cpf, averbadora, codigo_convenio
            )

        elif averbadora == NomeAverbadoras.SERPRO.value:
            serpro = Serpro(averbadora=averbadora)
            matricula, erro = serpro.registrations_consult(
                cpf=numero_cpf, codigo_convenio=codigo_convenio
            )

        if matricula:
            if averbadora == NomeAverbadoras.QUANTUM.value:
                serializer = ConsultaMatriculaQuantumSerializer(matricula)
            elif averbadora == NomeAverbadoras.FACIL.value:
                serializer = ConsultaMatriculaFacilSerializer(matricula, many=True)
            else:
                serializer = ConsultaMatriculaSerializer(matricula, many=True)
            return Response(serializer.data, status=HTTP_200_OK)

        elif averbadora == NomeAverbadoras.FACIL.value and erro is None:
            logger.error(
                'O cliente informado está registrado em um sub-órgão não atendido',
                exc_info=True,
            )
            return Response(
                {'O cliente informado está registrado em um sub-órgão não atendido'},
                status=HTTP_400_BAD_REQUEST,
            )
        elif erro == 'Erro_Consulta':
            logger.error('Não foi possível consultar a matrícula.', exc_info=True)
            return Response(
                {'Não foi possível consultar a matrícula.'}, status=HTTP_400_BAD_REQUEST
            )
        elif erro == 'Erro_Filtrar':
            logger.error('Não foi possivel buscar a matricula.', exc_info=True)
            return Response(
                {'Não foi possivel buscar a matricula'}, status=HTTP_400_BAD_REQUEST
            )
        elif erro == 'SubOrgao_Vazio':
            logger.error(
                'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio para essa '
                'averbadora',
                exc_info=True,
            )
            return Response(
                {
                    'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio '
                    'para essa averbadora'
                },
                status=HTTP_400_BAD_REQUEST,
            )


@api_view(['POST', 'GET'])
@permission_classes((HasAPIKeyOrAllowAny,))
def margem_view(request):
    logger = logging.getLogger('digitacao')

    if request.method == 'POST':
        numero_cpf = request.data.get('numero_cpf')
        averbadora = request.data.get('averbadora')
        codigo_convenio = request.data.get('convenio')

        numero_matricula = request.data.get('numero_matricula')
        senha_servidor = request.data.get('senha_servidor')

        if averbadora == NomeAverbadoras.FACIL.value:
            matricula, erro = consulta_matricula(
                numero_cpf, averbadora, codigo_convenio, numero_matricula
            )
            if matricula:
                matricula = filter_valid_margins(matricula, codigo_convenio, averbadora)
                serializer = ConsultaMatriculaFacilSerializer(matricula, many=True)
                return Response(serializer.data, status=HTTP_200_OK)

            elif averbadora == NomeAverbadoras.FACIL.value and erro is None:
                logger.error(
                    'O cliente informado está registrado em um sub-órgão não atendido',
                    exc_info=True,
                )
                return Response(
                    {
                        'O cliente informado está registrado em um sub-órgão não atendido'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            elif erro == 'Erro_Consulta':
                logger.error('Não foi possível consultar a matrícula.', exc_info=True)
                return Response(
                    {'Não foi possível consultar a matrícula.'},
                    status=HTTP_400_BAD_REQUEST,
                )
            elif erro == 'Erro_Filtrar':
                logger.error('Não foi possivel buscar a matricula.', exc_info=True)
                return Response(
                    {'Não foi possivel buscar a matricula'}, status=HTTP_400_BAD_REQUEST
                )
            elif erro == 'Consignacao_Ativa':
                logger.error('A matrícula informada possui consignações ativas.')
                return Response(
                    {'Erro': 'A matrícula informada possui consignações ativas.'},
                    status=HTTP_400_BAD_REQUEST,
                )
            elif erro == 'SubOrgao_Vazio':
                logger.error(
                    'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio para essa '
                    'averbadora',
                    exc_info=True,
                )
                return Response(
                    {
                        'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio '
                        'para essa averbadora'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            elif erro == 'Erro_Matricula_Nao_Encontrada':
                logger.error(
                    f'Não foi encontrado margem para a matrícula solicitada {numero_matricula}.'
                )
                return Response(
                    {'Não foi encontrado margem para a matrícula solicitada'},
                    status=HTTP_400_BAD_REQUEST,
                )

        consignacoes = None

        # if averbadora == NomeAverbadoras.ZETRASOFT.value:
        #     zetra = Zetra(averbadora_number=averbadora, convenio_code=codigo_convenio)
        #     consignacoes = zetra.consignment_consult(
        #         cpf=numero_cpf, registration_number=numero_matricula
        #     )

        if averbadora == NomeAverbadoras.QUANTUM.value:
            consignacoes = consulta_consignacoes_quantum(
                numero_cpf, averbadora, codigo_convenio
            )

        # serializer = ConsultaConsignacaoSerializer(consignacoes)
        if (
            averbadora == NomeAverbadoras.SERPRO.value
            or averbadora == NomeAverbadoras.NEOCONSIG.value
            or averbadora == NomeAverbadoras.ZETRASOFT.value
            or (
                consignacoes
                and consignacoes.descricao
                == 'Não existem consignações para esses dados'
            )
        ):
            if averbadora == NomeAverbadoras.ZETRASOFT.value:
                zetra = Zetra(
                    averbadora_number=averbadora, convenio_code=codigo_convenio
                )
                margem = zetra.margins_consult(
                    cpf=numero_cpf,
                    registration_number=numero_matricula,
                    server_password=senha_servidor,
                )

                if isinstance(margem, dict):
                    return Response(
                        {'Erro': margem.get('descricao')},
                        status=HTTP_400_BAD_REQUEST,
                    )

                margem = filter_valid_margins(margem, codigo_convenio, averbadora)

            elif averbadora == NomeAverbadoras.QUANTUM.value:
                margem = consulta_margem_quantum(
                    numero_cpf, averbadora, codigo_convenio
                )

            elif averbadora == NomeAverbadoras.SERPRO.value:
                serpro = Serpro(averbadora=averbadora)
                margem = serpro.margins_consult(
                    cpf=numero_cpf,
                    codigo_convenio=codigo_convenio,
                    numero_matricula=numero_matricula,
                )

                if not len(margem) and 'descricao' not in margem:
                    return Response(
                        {'Erro': 'Sem margem para a matrícula  solicitada.'},
                        status=HTTP_400_BAD_REQUEST,
                    )

                margem = filter_valid_margins(margem, codigo_convenio, averbadora)

            elif averbadora == NomeAverbadoras.NEOCONSIG.value:
                neoconsig = Neoconsig(averbadora=averbadora)
                margem = neoconsig.margins_consult(
                    cpf=numero_cpf,
                    codigo_convenio=codigo_convenio,
                    numero_matricula=numero_matricula,
                )

                if 'descricao' in margem:
                    return Response(
                        {'Erro': 'Erro ao consultar margem.'},
                        status=HTTP_400_BAD_REQUEST,
                    )

                if not len(margem):
                    return Response(
                        {'Erro': 'Sem margem para a matrícula ou cpf solicitada.'},
                        status=HTTP_400_BAD_REQUEST,
                    )

                margem = filter_valid_margins(margem, codigo_convenio, averbadora)
                margem = ConsultaMatriculaFacilSerializer(margem, many=True)
                return Response(margem.data, status=HTTP_200_OK)

            if 'descricao' in margem:
                return Response(
                    {'Erro': 'Matrícula, folha, CPF ou verba inválidos.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            if averbadora == NomeAverbadoras.QUANTUM.value:
                serializer_margem = ConsultaMargemQuantumSerializer(margem)

            elif averbadora == NomeAverbadoras.ZETRASOFT.value:
                serializer_margem = ConsultaMargemZetraSerializer(margem, many=True)

            elif averbadora == NomeAverbadoras.SERPRO.value:
                serializer_margem = ConsultaMargemSerproSerializer(margem, many=True)

            else:
                serializer_margem = ConsultaMargemSerializer(margem, many=True)

            return Response(serializer_margem.data, status=HTTP_200_OK)

        elif consignacoes.descricao is None:
            return Response(
                {'Erro': 'A matrícula possui consignações ativas.'},
                status=HTTP_400_BAD_REQUEST,
            )

        elif consignacoes.descricao == 'Os dados fornecidos são inválidos':
            return Response(
                {'Erro': 'Os dados fornecidos são inválidos.'},
                status=HTTP_400_BAD_REQUEST,
            )

    return Response(
        {'Erro': 'Os dados fornecidos são inválidos.'}, status=HTTP_400_BAD_REQUEST
    )


@api_view(['POST', 'GET'])
def realiza_reserva_view(request):
    if request.method != 'POST':
        return Response(
            {'Erro': 'Os dados fornecidos são inválidos.'}, status=HTTP_400_BAD_REQUEST
        )
    numero_cpf = request.data.get('numero_cpf')
    averbadora = request.data.get('averbadora')
    valor = request.data.get('valor')
    codigo_convenio = request.data.get('convenio')
    contrato_id = request.data.get('contrato_id')
    senha_servidor = request.data.get('senha_servidor')
    verba = request.data.get('verba')

    contrato = Contrato.objects.get(pk=contrato_id)

    if averbadora == NomeAverbadoras.FACIL.value:
        reserva = realiza_reserva(numero_cpf, averbadora, codigo_convenio, contrato)

    elif averbadora == NomeAverbadoras.ZETRASOFT.value:
        zetra = Zetra(averbadora_number=averbadora, convenio_code=codigo_convenio)
        reserva = zetra.margin_reserve(
            cpf=numero_cpf,
            server_password=senha_servidor,
            verba=verba,
            registration_number=contrato.cliente.numero_matricula,
        )

    elif averbadora == NomeAverbadoras.QUANTUM.value:
        reserva = reservar_margem_quantum(
            numero_cpf, averbadora, valor, codigo_convenio
        )

    elif averbadora == NomeAverbadoras.DATAPREV_BRB.value:
        token_envelope = request.data['token_envelope']
        contrato = Contrato.objects.get(token_envelope=token_envelope)
        reserva = reserva_margem_inss(numero_cpf, averbadora, contrato, valor)

    elif averbadora == NomeAverbadoras.SERPRO.value:
        serpro = Serpro(averbadora=averbadora)

        token_envelope = request.data['token_envelope']
        contrato = Contrato.objects.get(token_envelope=token_envelope)

        valor_limte_cartao = float(round(contrato.limite_pre_aprovado, 2))

        reserva = serpro.margin_reserve(
            cpf=numero_cpf,
            registration_number=contrato.cliente.numero_matricula,
            contract_id=contrato.id,
            card_limit_value=valor_limte_cartao,
            codigo_convenio=codigo_convenio,
        )

    elif averbadora == NomeAverbadoras.NEOCONSIG.value:
        neoconsig = Neoconsig(averbadora=averbadora)
        reserva = neoconsig.margin_reserve_and_confirmation(
            numero_cpf, averbadora, codigo_convenio, contrato
        )

    if settings.ORIGIN_CLIENT == 'BRB':
        atualizacao_cadastral.apply_async(args=[numero_cpf])

    if not reserva.reserva:
        return Response(
            {'Erro': 'Não foi possível realizar a reserva.'},
            status=HTTP_400_BAD_REQUEST,
        )
    if averbadora == NomeAverbadoras.QUANTUM.value:
        serializer = RealizaReservaQuantumSerializer(reserva)
    elif averbadora == NomeAverbadoras.DATAPREV_BRB.value:
        serializer = RealizaReservaDataprevSerializer(reserva)
    else:
        serializer = RealizaReservaSerializer(reserva)

    return Response(serializer.data, status=HTTP_200_OK)


@api_view(['POST', 'GET'])
def cancela_reserva_view(request):
    if request.method == 'POST':
        numero_cpf = request.data.get('numero_cpf')
        numero_matricula = request.data.get('numero_matricula')
        reserva = request.data.get('reserva')
        averbadora = request.data.get('averbadora')
        codigo_convenio = request.data.get('convenio')
        # TODO: ver se front tem informação abaixo
        contract_id = request.data.get('contract_id')

        if reserva:
            if averbadora == NomeAverbadoras.FACIL.value:
                cancelar_reserva = cancela_reserva(
                    numero_cpf,
                    numero_matricula,
                    averbadora,
                    codigo_convenio,
                    contract_id,
                )

            elif averbadora == NomeAverbadoras.ZETRASOFT.value:
                zetra = Zetra(
                    averbadora_number=averbadora, convenio_code=codigo_convenio
                )
                cancelar_reserva = zetra.margin_reserve_cancel(cpf=numero_cpf)

            elif averbadora == NomeAverbadoras.QUANTUM.value:
                cancelar_reserva = cancela_reserva_quantum(
                    numero_cpf, averbadora, codigo_convenio
                )

            elif averbadora == NomeAverbadoras.SERPRO.value:
                serpro = Serpro(averbadora=averbadora)
                cancelar_reserva = serpro.margin_reserve_cancel(
                    cpf=numero_cpf,
                    registration_number=numero_matricula,
                    contract_id=contract_id,
                    codigo_convenio=codigo_convenio,
                )

            elif averbadora == NomeAverbadoras.NEOCONSIG.value:
                neoconsig = Neoconsig(averbadora=averbadora)
                cancelar_reserva = neoconsig.cancel_margin_reserve(
                    cpf=numero_cpf,
                    codigo_convenio=codigo_convenio,
                    averbadora=averbadora,
                    contrato=contract_id,
                )

            if not cancelar_reserva.reserva:
                return Response(
                    {
                        'Erro': f'Não foi possível cancelar a reserva. {cancelar_reserva.descricao}'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            serializer = (
                CancelaReservaQuantumSerializer(cancelar_reserva)
                if averbadora == NomeAverbadoras.QUANTUM.value
                else CancelaReservaSerializer(cancelar_reserva)
            )
            return Response(serializer.data, status=HTTP_200_OK)
    return Response(
        {'Erro': 'Os dados fornecidos são inválidos.'}, status=HTTP_400_BAD_REQUEST
    )


@api_view(['POST', 'GET'])
@permission_classes([HasAPIKey | IsAuthenticated])
def simulacao_limite_view(request):
    logger = logging.getLogger('digitacao')

    data = {}
    # dados_adicionais = {}

    try:
        if request.method == 'POST':
            numero_cpf = request.data['numero_cpf']
            codigo_convenio = request.data['convenio']
            tipo_produto = request.data.get('tipo_produto')  # TODO AQUI
            data_nascimento_str = request.data.get('data_nascimento')  # TODO AQUI
            valor_margem_cliente = request.data.get('margem')  # TODO AQUI
            id_cliente_cartao = request.data.get('id_cliente_cartao')
            valor_compra_unificada = request.data.get(
                'valor_compra_unificada'
            )  # TODO CASO SEJA MARGEM UNIFICADA RECEBO VALOR_COMPRA
            valor_saque_unificada = request.data.get(
                'valor_saque_unificada'
            )  # TODO CASO SEJA MARGEM UNIFICADA RECEBO VALOR_COMPRA
            tipo_vinculo = request.data.get('tipo_vinculo')

            # Verifica se o cliente possui margem unificada
            cliente_cartao = ClienteCartaoBeneficio.objects.get(id=id_cliente_cartao)
            if cliente_cartao.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA and (
                not valor_compra_unificada or not valor_saque_unificada
            ):
                return JsonResponse(
                    {
                        'error': 'Campos valor_compra_unificada e valor_saque_unificada são '
                        'obrigatórios para margem unificada.'
                    },
                    status=400,
                )

            # Criando a instância da classe Simulacao
            simulador = Simulacao(
                codigo_convenio,
                tipo_produto,
                data_nascimento_str,
                valor_margem_cliente,
                numero_cpf,
                id_cliente_cartao,
                Decimal(valor_compra_unificada) if valor_compra_unificada else None,
                Decimal(valor_saque_unificada) if valor_saque_unificada else None,
                tipo_vinculo or None,
            )
            possui_saque = False

            if valor_compra_unificada and valor_saque_unificada:
                resultado_saque = simulador.processar_margem_saque()
                resultado_compra = simulador.processar_margem_compra()

                if 'error' in resultado_saque:
                    # Se o resultado contém a chave 'error', retornamos ela.
                    return JsonResponse({'error': resultado_saque['error']}, status=400)

                if 'error' in resultado_compra:
                    # Se o resultado contém a chave 'error', retornamos ela.
                    return JsonResponse(
                        {'error': resultado_compra['error']}, status=400
                    )

                resultado = simulador.realizar_simulacao_margem_unificada(
                    possui_saque=possui_saque
                )

                try:
                    data = {
                        'simulacao_data': resultado[0],
                        'dados_adicionais': resultado[1],
                        'simulacao': resultado[2],
                    }
                    return JsonResponse(data, status=200)
                except Exception as e:
                    print(e)
                    return JsonResponse(resultado, status=404)
            else:
                # Chamando o método realizar() da classe
                resultado = simulador.realizar(possui_saque=possui_saque)
                if 'error' in resultado:
                    # Se o resultado contém a chave 'error', retornamos ela.
                    return JsonResponse({'error': resultado['error']}, status=400)

                # Se chegamos aqui, significa que temos uma simulação válida
                data = {
                    'simulacao_data': resultado[0],
                    'dados_adicionais': resultado[1],
                    'simulacao': resultado[2],
                }
                return JsonResponse(data, status=200)

    except Exception as e:
        logger.error(f'{e} - {e.__traceback__.tb_lineno}')
        data['error'] = str(e)
        return JsonResponse(data, status=500)


class SimulacaoSaqueComplementar(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]
    serializer_class = AtualizarClienteSerializer

    def post(self, request):
        numero_cpf = request.data['numero_cpf']
        valor = request.data['valor']
        qtd_parcelas = request.data.get('qtd_parcelas')
        id_cliente_cartao = request.data.get('id_cliente_cartao')

        try:
            cliente = consulta_cliente(numero_cpf)
            cliente_cartao = ClienteCartaoBeneficio.objects.filter(
                pk=id_cliente_cartao
            ).first()
            convenio = Convenios.objects.filter(
                pk=cliente_cartao.convenio.pk, ativo=True
            ).first()

            produto_convenio = ProdutoConvenio.objects.filter(
                convenio=convenio, produto=cliente_cartao.tipo_produto
            ).first()

            if not produto_convenio:
                return Response(
                    {
                        'Erro': 'O convênio solicitado não possui o produto saque complementar.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            response = limites_disponibilidades(
                cliente_cartao.id_cartao_dock, cliente, cliente_cartao.pk
            )

            contratos = Contrato.objects.filter(cliente=cliente)
            for contrato in contratos:
                if contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
                elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_cartao = SaqueComplementar.objects.get(contrato=contrato)

                if contrato_cartao.status in (
                    ContractStatus.PENDENTE_DOCUMENTACAO.value,
                    ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value,
                    ContractStatus.APROVADA_MESA_CORBAN.value,
                    ContractStatus.FORMALIZACAO_CLIENTE.value,
                    ContractStatus.APROVADA_FINALIZADA.value,
                    ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
                    ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                ):
                    if float(response['saldoDisponivelSaque']) > float(
                        contrato_cartao.valor_saque
                    ):
                        limite_disponivel_saque = float(
                            response['saldoDisponivelSaque']
                        ) - float(contrato_cartao.valor_saque)
                    else:
                        limite_disponivel_saque = float(
                            contrato_cartao.valor_saque
                        ) - float(response['saldoDisponivelSaque'])
                    break
                else:
                    limite_disponivel_saque = response['saldoDisponivelSaque']

            valor_minimo_saque_convenio = produto_convenio.vr_minimo_saque
            matricula = cliente_cartao.numero_matricula
            parametros_backoffice = ParametrosBackoffice.objects.filter(
                ativo=True, tipoProduto=EnumTipoProduto.SAQUE_COMPLEMENTAR
            ).first()
            simulacao = calcula_simulacao_iof_saque_complementar(
                valor, produto_convenio, parametros_backoffice
            )

            if qtd_parcelas is not None:
                simulacao_saque_parcelado = simulacao_saque_parcelado_dock(
                    qtd_parcelas,
                    valor,
                    produto_convenio,
                    cliente,
                    parametros_backoffice,
                )
            else:
                simulacao_saque_parcelado = {}

            permite_saque = produto_convenio.permite_saque
            permite_saque_parcelado = produto_convenio.permite_saque_parcelado

            if not permite_saque and not permite_saque_parcelado:
                return Response(
                    {'Erro': 'O convênio solicitado não permite saque'},
                    status=HTTP_400_BAD_REQUEST,
                )

            if (
                not valor_minimo_saque_convenio
                < simulacao['valor_saque']
                <= limite_disponivel_saque
            ):
                return Response(
                    {
                        'Erro': 'O valor informado não atende aos requisitos parametrizado.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
            try:
                RealizaSimulacao.objects.create(
                    log_api=log_api_id,
                    cliente=cliente,
                    matricula=matricula,
                    valor_saque=simulacao['valor_saque'],
                )
            except Exception as e:
                print(e)
                RealizaSimulacao.objects.create(
                    log_api=log_api_id.pk,
                    cliente=cliente,
                    matricula=matricula,
                    valor_saque=simulacao['valor_saque'],
                )

            return Response(
                (
                    simulacao,
                    {'simulacao_saque_parcelado': simulacao_saque_parcelado},
                ),
                status=HTTP_200_OK,
            )
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao processar a simulação.'},
                status=HTTP_400_BAD_REQUEST,
            )


@api_view(['POST', 'GET'])
@permission_classes([HasAPIKey | IsAuthenticated])
def simulacao_saque_view(request):
    data = {}
    try:
        if request.method == 'POST':
            numero_cpf = request.data.get('numero_cpf')
            valor = float(request.data.get('valor'))
            id_convenio = request.data.get('convenio')
            qtd_parcelas = request.data.get('qtd_parcelas')
            tipo_produto = request.data.get('tipo_produto')
            tipo_margem = request.data.get('tipo_margem')
            margem = request.data.get('margem')
            id_cliente_cartao = request.data.get('id_cliente_cartao')

            if f'{tipo_margem}' == f'{EnumTipoMargem.MARGEM_UNIFICADA}':
                tipo_margem = EnumTipoMargem.MARGEM_SAQUE

            convenio = Convenios.objects.filter(pk=id_convenio, ativo=True).first()
            produto_convenio = ProdutoConvenio.objects.filter(
                convenio=convenio, produto=tipo_produto, tipo_margem=tipo_margem
            ).first()
            logger.info('Convenio: ' + str(convenio))
            logger.info('Id Cliente Cartao: ' + str(id_cliente_cartao))
            cliente_cartao = ClienteCartaoBeneficio.objects.get(id=id_cliente_cartao)
            logger.info('Cliente cartao: ' + str(cliente_cartao))
            idade_cliente = calcular_idade(cliente_cartao.cliente.dt_nascimento)
            logger.info('Idade cliente: ' + str(idade_cliente))
            if siape := RegrasIdade.objects.filter(
                ativo=True,
                tipo_vinculo_siape=cliente_cartao.tipo_vinculo_siape,
                convenio=convenio,
            ).first():
                regra_idades = RegrasIdade.objects.filter(
                    convenio=convenio,
                    produto=tipo_produto,
                    ativo=True,
                    tipo_vinculo_siape=cliente_cartao.tipo_vinculo_siape,
                )
            else:
                regra_idades = RegrasIdade.objects.filter(
                    convenio=convenio,
                    produto=tipo_produto,
                    ativo=True,
                )

            for range in regra_idades:
                if range.idade_minima <= idade_cliente <= range.idade_maxima:
                    regra_idade = RegrasIdade.objects.get(id=range.pk)

            cliente_cartao = ClienteCartaoBeneficio.objects.get(id=id_cliente_cartao)
            registro_regras = 0
            try:
                try:
                    tipo_vinculo = cliente_cartao.tipo_vinculo_siape
                    siape = RegrasIdade.objects.filter(
                        ativo=True,
                        tipo_vinculo_siape=tipo_vinculo,
                        convenio=convenio.pk,
                    ).first()
                except AttributeError:
                    tipo_vinculo = ''
                    siape = False
                if siape:
                    regra_idades = RegrasIdade.objects.filter(
                        convenio=convenio,
                        produto=tipo_produto,
                        ativo=True,
                        tipo_vinculo_siape=cliente_cartao.tipo_vinculo_siape,
                    )
                else:
                    regra_idades = RegrasIdade.objects.filter(
                        convenio=convenio, produto=tipo_produto, ativo=True
                    )

                for range in regra_idades:
                    if range.idade_minima <= idade_cliente <= range.idade_maxima:
                        registro_regras += 1
                        regra_idade = RegrasIdade.objects.get(id=range.pk)

                if registro_regras > 1:
                    return Response(
                        {'error': 'Parâmetro de regra de idade duplicada'},
                        status=HTTP_404_NOT_FOUND,
                    )
                elif registro_regras == 0:
                    return Response(
                        {
                            'error': 'Cliente não atende os requisitos de idade para contratação'
                        },
                        status=HTTP_404_NOT_FOUND,
                    )
            except RegrasIdade.DoesNotExist:
                return Response(
                    {
                        'error': 'Não existem parâmetros de idade para o tipo de produto escolhido'
                    },
                    status=HTTP_404_NOT_FOUND,
                )

            cliente = consulta_cliente(numero_cpf)
            cliente_cartao, _ = ClienteCartaoBeneficio.objects.get_or_create(
                pk=id_cliente_cartao
            )
            matricula = cliente_cartao.numero_matricula

            valor_margem_cliente = Decimal(str(margem))
            valor_maximo_margem_convenio = produto_convenio.margem_maxima
            valor_minimo_margem_convenio = produto_convenio.margem_minima
            valor_minimo_saque_convenio = produto_convenio.vr_minimo_saque

            parametros_backoffice = ParametrosBackoffice.objects.filter(
                ativo=True, tipoProduto=tipo_produto
            ).first()

            possui_saque = True
            simulacao = calcula_simulacao_iof(
                valor,
                produto_convenio,
                parametros_backoffice,
                possui_saque=possui_saque,
            )

            if qtd_parcelas is not None:
                simulacao_saque_parcelado = simulacao_saque_parcelado_dock(
                    qtd_parcelas,
                    valor,
                    produto_convenio,
                    cliente,
                    parametros_backoffice,
                )
                if valor_margem_cliente < simulacao_saque_parcelado.get(
                    'valor_parcela', 0
                ):
                    return Response(
                        {'Erro': 'Valor da parcela superior a margem disponível'},
                        status=HTTP_400_BAD_REQUEST,
                    )

            else:
                simulacao_saque_parcelado = {}

            fator = regra_idade.fator
            percentual_saque = produto_convenio.percentual_saque / 100

            if not (
                valor_minimo_margem_convenio
                <= valor_margem_cliente
                <= valor_maximo_margem_convenio
            ):
                return Response(
                    {
                        'Erro': 'A matrícula informada não preenche os requisitos de margem necessários.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            limite_pre_aprovado = round(valor_margem_cliente * fator, 2)
            if limite_pre_aprovado > regra_idade.limite_maximo_credito:
                limite_pre_aprovado = regra_idade.limite_maximo_credito
            elif limite_pre_aprovado < regra_idade.limite_minimo_credito:
                return {
                    'error': 'Cliente não atende os requisitos de idade para contratação'
                }

            permite_saque = produto_convenio.permite_saque
            permite_saque_parcelado = produto_convenio.permite_saque_parcelado
            if not permite_saque and not permite_saque_parcelado:
                return Response(
                    {'Erro': 'O convênio solicitado não permite saque'},
                    status=HTTP_400_BAD_REQUEST,
                )
            # Calcula o valor permitido para o saque de acordo com o limite do cartão
            valor_disponivel_saque = limite_pre_aprovado * percentual_saque
            # RETORNO DO VALOR CET_AM e CET_AA sobre o valor de saque
            valor_maximo_saque_convenio = limite_pre_aprovado * (
                produto_convenio.percentual_saque / 100
            )
            simulacao['valor_disponivel_saque'] = valor_maximo_saque_convenio

            if valor_minimo_saque_convenio >= valor_disponivel_saque:
                return Response(
                    {
                        'Erro': 'O valor do saque não  está de acordo com as regras estabelecidas '
                        'pelo convênio.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            if not convenio.convenio_inss and not convenio.digitacao_manual:
                (
                    log_api_id,
                    _,
                ) = LogCliente.objects.get_or_create(cliente=cliente)
                try:
                    RealizaSimulacao.objects.create(
                        log_api=log_api_id,
                        cliente=cliente,
                        matricula=matricula,
                        limite_pre_aprovado=limite_pre_aprovado,
                        valor_saque=valor_disponivel_saque,
                    )
                except Exception as e:
                    logger.error(
                        f'Something wrong with the creation of RealizaSimulacao, {e}'
                    )
                    RealizaSimulacao.objects.create(
                        log_api=log_api_id.pk,
                        cliente=cliente,
                        matricula=matricula,
                        limite_pre_aprovado=limite_pre_aprovado,
                        valor_saque=valor_disponivel_saque,
                    )
            else:
                if limite_pre_aprovado > regra_idade.limite_maximo_credito:
                    return Response(
                        {
                            'Erro': 'O valor do saque não  está de acordo com as regras estabelecidas '
                            'pelo convênio.'
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )
                (
                    log_api_id,
                    _,
                ) = LogCliente.objects.get_or_create(cliente=cliente)
                try:
                    RealizaSimulacao.objects.create(
                        log_api=log_api_id,
                        cliente=cliente,
                        matricula=matricula,
                        limite_pre_aprovado=limite_pre_aprovado,
                        valor_saque=valor_disponivel_saque,
                    )
                except Exception as e:
                    print(e)
                    RealizaSimulacao.objects.create(
                        log_api=log_api_id.pk,
                        cliente=cliente,
                        matricula=matricula,
                        limite_pre_aprovado=limite_pre_aprovado,
                        valor_saque=valor_disponivel_saque,
                    )
            return Response(
                (
                    simulacao,
                    {'simulacao_saque_parcelado': simulacao_saque_parcelado},
                ),
                status=HTTP_200_OK,
            )
    except Exception as e:
        print(e)
        return Response(
            {'Erro': 'Ocorreu um erro ao processar a simulação.'},
            status=HTTP_400_BAD_REQUEST,
        )

    return Response(data, status=(HTTP_500_INTERNAL_SERVER_ERROR))


class PlanosAPIView(GenericAPIView):
    def get(self, request):
        planos = Planos.objects.filter(ativo=True)
        serializer = PlanosSerializer(planos, many=True)
        return Response(serializer.data)


class InsuranceByAgreementView(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        try:
            agreement_id = request.data.get('id_convenio')
            product_id = request.data.get('id_produto')
            card_limit = Decimal(request.data.get('limite_cartao'))
            insurance_data_agent = InsuranceDataAgent()
            insurances = insurance_data_agent.get_insurance_by_agreement_and_product(
                agreement_id, product_id
            )
            sorted_insurance_plans = (
                insurance_data_agent.calculate_and_sort_insurance_plans(
                    insurances, card_limit
                )
            )
            serializer = PlanosSerializerSeguradora(sorted_insurance_plans, many=True)
            return Response(serializer.data, status=HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


class AtualizarContratoSaque(UpdateAPIView):
    serializer_class = ContratoSaqueSerializer

    def patch(self, request, *args, **kwargs):
        payload = request.data

        try:
            token_contrato = request.data['token_contrato']
            contrato = Contrato.objects.get(token_contrato=token_contrato)
            cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)
            contrato_serializer = ContratoSaqueSerializer(
                contrato, data=payload, partial=True
            )
            cartao_beneficio_serializer = CartaoBeneficioSerializer(
                cartao_beneficio, data=payload, partial=True
            )
            if (
                contrato_serializer.is_valid()
                and cartao_beneficio_serializer.is_valid()
            ):
                cartao_beneficio_set = cartao_beneficio_serializer.save()
                contrato_set = contrato_serializer.save()

                if contrato_set and cartao_beneficio_set:
                    contrato.status = EnumContratoStatus.DIGITACAO
                    cartao_beneficio.status = ContractStatus.ANDAMENTO_SIMULACAO.value
                    cartao_beneficio.save()
                    contrato.save()
                    return Response(
                        {'msg': 'Contrato atualizado com sucesso.'}, status=HTTP_200_OK
                    )
                else:
                    return Response(
                        {
                            'msg': 'Ocorreu um erro ao realizar a chamada, contate o suporte.'
                        },
                        status=HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                erros = contrato_serializer.errors | cartao_beneficio_serializer.errors
                return Response(erros, status=HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {'msg': 'Ocorreu um erro ao realizar a chamada, contate o suporte.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Pesquisa o contrato através do token de formalização
class VerificaCartaoCliente(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        cpf_cliente = request.data.get('numero_cpf')

        try:
            cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
            contratos = Contrato.objects.filter(
                cliente=cliente,
                tipo_produto__in=(
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                    EnumTipoProduto.CARTAO_BENEFICIO,
                ),
                contrato_cartao_beneficio__status__in=[
                    ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                    ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                    ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
                    ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                    ContractStatus.SAQUE_CANCELADO_LIMITE_DISPONIVEL_INSUFICIENTE.value,
                    ContractStatus.SAQUE_RECUSADO_PROBLEMA_PAGAMENTO.value,
                ],
            )
            if not contratos.exists():
                return Response(
                    {'detail': 'Não foram encontrados contratos para esse cliente.'},
                    status=200,
                )

            cartoes = []
            for contrato in contratos:
                envelope = EnvelopeContratos.objects.get(
                    token_envelope=contrato.token_envelope
                )
                cliente_cartao = contrato.cliente_cartao_contrato.get()
                contrato_cartao = contrato.contrato_cartao_beneficio.get()
                cartao_info = {'cartao_criado': True}
                if cliente_cartao.id_cartao_dock is None:
                    cartao_info['cartao_criado'] = False
                cartao_info['id_registro_dock'] = cliente_cartao.id_registro_dock
                cartao_info['id_conta_dock'] = cliente_cartao.id_conta_dock
                cartao_info['id_cartao_dock'] = cliente_cartao.id_cartao_dock
                cartao_info['id_endereco_dock'] = cliente_cartao.id_endereco_dock
                cartao_info['id_telefone_dock'] = cliente_cartao.id_telefone_dock
                cartao_info['id_processo_unico'] = (
                    envelope.id_processo_unico or 'Cliente não possui registro'
                )
                cartao_info['token_envelope'] = str(contrato.token_envelope)
                cartao_info['codigo_convenio'] = cliente_cartao.convenio.pk
                cartao_info['nome_convenio'] = cliente_cartao.convenio.nome
                cartao_info['bandeira_cartao'] = 'Visa'
                cartao_info['produto_codigo'] = cliente_cartao.tipo_produto

                cartao_info['possui_seguro_prata'] = False
                cartao_info['possui_seguro_ouro'] = False
                cartao_info['possui_seguro_diamante'] = False
                for plano_contrato in BeneficiosContratado.objects.select_related(
                    'plano'
                ).filter(cliente=cliente_cartao.cliente):
                    if plano_contrato.plano.tipo_plano == EnumTipoPlano.PRATA:
                        cartao_info['possui_seguro_prata'] = True
                    elif plano_contrato.plano.tipo_plano == EnumTipoPlano.OURO:
                        cartao_info['possui_seguro_ouro'] = True
                    elif plano_contrato.plano.tipo_plano == EnumTipoPlano.DIAMANTE:
                        cartao_info['possui_seguro_diamante'] = True
                try:
                    cartao_info['numero_cartao'] = cliente_cartao.numero_cartao_dock[
                        -4:
                    ]
                    cartao_info['tipo_margem'] = cliente_cartao.tipo_margem
                    cartao_info['tipo_cartao'] = contrato_cartao.tipo_cartao
                except Exception:
                    cartao_info['numero_cartao'] = None
                    cartao_info['tipo_margem'] = None
                    cartao_info['tipo_cartao'] = None
                cartao_info['id_cliente_cartao'] = cliente_cartao.pk

                cartoes.append(cartao_info)

            convenio = Convenios.objects.get(pk=cliente_cartao.convenio.pk)
            serializer = RetornaCartaoExistente(cartoes, many=True)
            data = {
                'cartoes': serializer.data,
                'apto_saque': convenio.permite_saque_complementar,
            }
            return Response(data)

        except Cliente.DoesNotExist:
            return Response(
                {
                    'cartao_criado': False,
                    'Erro': 'Não foi possível encontrar o cartão do cliente.',
                },
                status=HTTP_200_OK,
            )
        except Exception as e:
            print(e)
            return Response({'Erro': 'Erro interno do servidor.'}, status=500)


# VALIDA ELEGIBILIDADE PARA SAQUE COMPLEMENTAR
def elegibilidade_saque_complementar(cliente, contrato):
    resposta_dock = {}
    resposta_account_dock = consulta_conta_dock(cliente, contrato)
    resposta_card_dock = consulta_cartao_dock(cliente, contrato)
    try:
        if resposta_account_dock['ConsultaRealizada']:
            if resposta_account_dock['idStatusConta'] in [
                StatusAccountDock.NORMAL.value,
                StatusAccountDock.LANCADO.value,
            ]:
                if resposta_card_dock == 'error':
                    resposta_dock['account_status'] = resposta_account_dock[
                        'idStatusConta'
                    ]
                    resposta_dock['card_status'] = 'erro na consulta do cartão'
                    resposta_dock['aprovada_saque_complementar'] = False
                elif resposta_card_dock in [
                    StatusCardDock.NORMAL_DESBLOQUEADO.value,
                    StatusCardDock.BLOQUEADO_PODE_SER_REVERTIDO.value,
                    StatusCardDock.CANCELADO_EXTRAVIADO.value,
                    StatusCardDock.CANCELADO_DANIFICADO.value,
                    StatusCardDock.CANCELADO_TARJA.value,
                    StatusCardDock.CANCELADO_EMBOSSING.value,
                ]:
                    resposta_dock['SaqueDisponivel'] = resposta_account_dock[
                        'SaqueDisponivel'
                    ]
                    resposta_dock['account_status'] = resposta_account_dock[
                        'idStatusConta'
                    ]
                    resposta_dock['card_status'] = resposta_card_dock
                    resposta_dock['aprovada_saque_complementar'] = True
                else:
                    resposta_dock['account_status'] = resposta_account_dock[
                        'idStatusConta'
                    ]
                    resposta_dock['card_status'] = resposta_card_dock
                    resposta_dock['aprovada_saque_complementar'] = False
            else:
                resposta_dock['account_status'] = resposta_account_dock['idStatusConta']
                resposta_dock['card_status'] = ''
                resposta_dock['aprovada_saque_complementar'] = False
        else:
            resposta_dock['account_status'] = 'Consulta não Realizada'
            resposta_dock['card_status'] = 'Consulta não Realizada'
            resposta_dock['aprovada_saque_complementar'] = False
    except Exception as e:
        resposta_dock['account_status'] = e
        resposta_dock['card_status'] = e
        resposta_dock['aprovada_saque_complementar'] = False
    return resposta_dock


# ConsultaLimiteSaque na dock para realizar saque complementar
class ConsultaLimiteSaque(GenericAPIView):
    permission_classes = [HasAPIKey | IsAuthenticated]

    def post(self, request):
        dados_adicionais = {}
        request.META.get('HTTP_ORIGIN')
        cpf_cliente = request.data['numero_cpf']
        id_cartao = request.data['id_cartao']
        id_cliente_cartao = request.data.get('id_cliente_cartao')

        # valida cliente cartao
        cliente_cartao = ClienteCartaoBeneficio.objects.get(id=id_cliente_cartao)
        registro_regras = 0
        idade_cliente = calcular_idade(cliente_cartao.cliente.dt_nascimento)
        siape = RegrasIdade.objects.filter(
            ativo=True,
            tipo_vinculo_siape=cliente_cartao.tipo_vinculo_siape,
            convenio=cliente_cartao.convenio,
        ).first()
        try:
            if siape:
                regra_idades = RegrasIdade.objects.filter(
                    convenio=cliente_cartao.convenio,
                    produto=cliente_cartao.tipo_produto,
                    ativo=True,
                    tipo_vinculo_siape=cliente_cartao.tipo_vinculo_siape,
                )
            else:
                regra_idades = RegrasIdade.objects.filter(
                    convenio=cliente_cartao.convenio,
                    produto=cliente_cartao.tipo_produto,
                    ativo=True,
                )

            for range in regra_idades:
                if range.idade_minima <= idade_cliente <= range.idade_maxima:
                    registro_regras += 1
                    regra_idade = RegrasIdade.objects.get(id=range.pk)

            if registro_regras > 1:
                return Response(
                    {'error': 'Parâmetro de regra de idade duplicada'},
                    status=HTTP_404_NOT_FOUND,
                )
            elif registro_regras == 0:
                return Response(
                    {
                        'error': 'Cliente não atende os requisitos de idade para contratação'
                    },
                    status=HTTP_404_NOT_FOUND,
                )
        except RegrasIdade.DoesNotExist:
            return Response(
                {
                    'error': 'Não existem parâmetros de idade para o tipo de cartão escolhido'
                },
                status=HTTP_404_NOT_FOUND,
            )

        try:
            parametro_backoffice = ParametrosBackoffice.objects.filter(
                tipoProduto=EnumTipoProduto.SAQUE_COMPLEMENTAR
            ).first()
            if not parametro_backoffice.ativo:
                apto_saque = False
                return Response(
                    {
                        'apto_saque': apto_saque,
                        'msg': 'Saque Complementar desligado.',
                    },
                    status=HTTP_200_OK,
                )
            cliente = Cliente.objects.get(nu_cpf=cpf_cliente)
            cliente_cartao = ClienteCartaoBeneficio.objects.filter(
                cliente=cliente, id_cartao_dock=id_cartao
            ).first()
            response = limites_disponibilidades(id_cartao, cliente, cliente_cartao.pk)
            convenio = Convenios.objects.get(pk=cliente_cartao.convenio.pk)

            produto_convenio = ProdutoConvenio.objects.filter(
                convenio=convenio, produto=cliente_cartao.tipo_produto
            ).first()
            response['valor_minimo_saque'] = produto_convenio.vr_minimo_saque

            # ID E NOME
            dados_adicionais['id'] = convenio.id
            dados_adicionais['nome'] = convenio.nome
            dados_adicionais['id_cliente_cartao'] = cliente_cartao.pk

            # PERMITE SAQUE
            dados_adicionais['permite_saque'] = produto_convenio.permite_saque
            dados_adicionais['permite_saque_parcelado'] = (
                produto_convenio.permite_saque_parcelado
            )

            total_descontado = 0

            contratos = Contrato.objects.filter(
                Q(cliente=cliente, cliente_cartao_contrato=id_cliente_cartao)
                | Q(
                    cliente=cliente,
                    contrato_saque_complementar__id_cliente_cartao=id_cliente_cartao,
                )
            )

            contrato_encontrado = False
            contrato_saque = None
            for contrato in contratos:
                if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
                elif contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    contrato_saque = CartaoBeneficio.objects.get(contrato=contrato)

                if contrato_saque and contrato_saque.status in (
                    ContractStatus.PENDENTE_DOCUMENTACAO.value,
                    ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value,
                    ContractStatus.APROVADA_MESA_CORBAN.value,
                    ContractStatus.ANDAMENTO_FORMALIZACAO.value,
                    ContractStatus.FORMALIZACAO_CLIENTE.value,
                    ContractStatus.APROVADA_FINALIZADA.value,
                    ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
                    ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                    ContractStatus.APROVADA_MESA_FORMALIZACAO.value,
                    ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
                    ContractStatus.CHECAGEM_MESA_CORBAN.value,
                    ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                ):
                    contrato_encontrado = True
                    if contrato_saque.valor_saque is not None:
                        total_descontado += float(contrato_saque.valor_saque)
                    else:
                        total_descontado += 0
            if contrato_encontrado:
                if float(response['saldoDisponivelSaque']) > float(total_descontado):
                    response['limite_disponivel_saque'] = float(
                        response['saldoDisponivelSaque']
                    ) - float(total_descontado)
                else:
                    response['limite_disponivel_saque'] = float(
                        total_descontado
                    ) - float(response['saldoDisponivelSaque'])

            else:
                response['limite_disponivel_saque'] = response['saldoDisponivelSaque']

            if float(response['limite_disponivel_saque']) < 0:
                response['limite_disponivel_saque'] = 0

            dados_adicionais['valor_minimo_saque_parcelado'] = (
                produto_convenio.saque_parc_val_total
            )
            if regra_idade:
                grupos_parcelas_saque_parcelado = [
                    regra_idade.grupo_parcelas,
                    regra_idade.grupo_parcelas_2,
                    regra_idade.grupo_parcelas_3,
                    regra_idade.grupo_parcelas_4,
                ]
                grupos_validos = [
                    grupo for grupo in grupos_parcelas_saque_parcelado if int(grupo) > 0
                ]
                grupos_validos_ordenados = sorted(grupos_validos, key=lambda x: int(x))
                dados_adicionais['grupos_parcelas_saque_parcelado'] = (
                    grupos_validos_ordenados
                )
            response['limite_utilizado_saque'] = round(
                response['limiteSaqueGlobal'] - response['saldoDisponivelSaque'], 2
            )
            # Add limite_total_saque and valor_maximo_saque
            response['limite_total_saque'] = response['limiteSaqueGlobal']
            response['valor_maximo_saque'] = response['limite_disponivel_saque']

            apto_saque = False

            if contratos_pendentes := Contrato.objects.filter(
                Q(cliente=cliente, cliente_cartao_contrato=id_cliente_cartao)
                | Q(
                    cliente=cliente,
                    contrato_saque_complementar__id_cliente_cartao=id_cliente_cartao,
                )
            ):
                for existe_contratos in contratos_pendentes:
                    if existe_contratos.tipo_produto in (
                        EnumTipoProduto.CARTAO_BENEFICIO,
                        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                    ):
                        contrato = CartaoBeneficio.objects.get(
                            contrato=existe_contratos
                        )
                        if contrato.status != ContractStatus.REPROVADA_FINALIZADA:
                            saque_complementar = elegibilidade_saque_complementar(
                                cliente, existe_contratos
                            )
                            if (
                                saque_complementar['aprovada_saque_complementar']
                                and int(saque_complementar['SaqueDisponivel']) > 50
                            ):
                                apto_saque = True

            apto_saque = apto_saque and convenio.permite_saque_complementar
            dados_adicionais['apto_saque'] = apto_saque
            response['apto_saque'] = apto_saque
            response['limite_pre_aprovado'] = response['limiteGlobal']

            serializer = LimitesDisponibilidadesSerializer(data=response)
            serializer.is_valid(raise_exception=True)
            transformed_response = serializer.validated_data

            return Response(
                (transformed_response, dados_adicionais), status=HTTP_200_OK
            )
        except Exception as e:
            print(e)
            apto_saque = False
            logger.error(f'Erro ao consultar limite de saque: {e}')
            return Response(
                {
                    'apto_saque': apto_saque,
                    'msg': 'Não foi possível consultar o limite de saque.',
                },
                status=HTTP_400_BAD_REQUEST,
            )


class CriarContratoSaqueComplementar(GenericAPIView):
    """
    API utilizada para a criação de um contrato durante a jornada de originação.
    """

    permission_classes = [HasAPIKey | IsAuthenticated]
    serializer_class = CriarContratoSaqueComplementarSerializer

    def post(self, request):
        cpf_cliente = request.data['numero_cpf']
        taxa_produto = request.data['taxa_produto']
        taxa_anual_produto = request.data['taxa_anual_produto']
        cet_mensal = request.data['cet_mensal']
        cet_anual = request.data['cet_anual']
        valor_iof_total = request.data['valor_iof_total']
        vr_iof_adicional = request.data['vr_iof_adicional']
        valor_iof_diario_em_dinheiro = request.data['valor_iof_diario_em_dinheiro']
        vencimento = request.data['vencimento']
        limite_disponivel_saque = request.data['limite_disponivel_saque']
        valor_lancado_fatura = request.data['valor_lancado_fatura']
        valor_saque = self.preserve_2_decimal_positions(
            float(request.data['valor_saque'])
        )
        saque_parcelado = request.data['saque_parcelado']
        possui_saque = request.data['possui_saque']
        valor_parcela = request.data['valor_parcela']
        qtd_parcela_saque_parcelado = request.data['qtd_parcela_saque_parcelado']
        valor_total_a_pagar = request.data['somatorio_parcelas']
        limite_pre_aprovado = request.data['limite_pre_aprovado']
        id_cliente_cartao = request.data['id_cliente_cartao']

        # parse the date string into a datetime object
        date_object = datetime.strptime(vencimento, '%Y-%m-%d')
        # extract the day
        day = date_object.day

        tipo_produto = EnumTipoProduto.SAQUE_COMPLEMENTAR
        tipo_contrato = EnumTipoContrato.SAQUE_COMPLEMENTAR
        cliente = Cliente.objects.filter(nu_cpf=cpf_cliente).first()

        try:
            identifier = (
                '00000000098' if request.user.is_anonymous else request.user.identifier
            )
            user = UserProfile.objects.get(identifier=identifier)
            inicio_digitacao = request.data['inicio_digitacao']
            envelope = EnvelopeContratos.objects.create(
                inicio_digitacao=inicio_digitacao
            )

            contrato = Contrato.objects.create(
                cliente=cliente,
                status=EnumContratoStatus.DIGITACAO,
                tipo_produto=tipo_produto,
                cd_contrato_tipo=tipo_contrato,
                token_envelope=envelope.token_envelope,
                created_by=user,
                corban=user.corban,
                corban_photo=user.corban.corban_name,
                created_by_photo=user.name,
                taxa_efetiva_mes=taxa_produto,
                taxa_efetiva_ano=taxa_anual_produto,
                cet_mes=cet_mensal,
                cet_ano=cet_anual,
                vr_iof_total=valor_iof_total,
                vr_iof=valor_iof_diario_em_dinheiro,
                vr_iof_adicional=vr_iof_adicional,
                vencimento_fatura=day,
                limite_pre_aprovado=limite_pre_aprovado,
            )

            id_cliente_cartao = ClienteCartaoBeneficio.objects.get(pk=id_cliente_cartao)

            SaqueComplementar.objects.create(
                contrato=contrato,
                status=ContractStatus.ANDAMENTO_SIMULACAO.value,
                valor_disponivel_saque=limite_disponivel_saque,
                valor_lancado_fatura=valor_lancado_fatura,
                valor_saque=valor_saque,
                saque_parcelado=saque_parcelado,
                possui_saque=possui_saque,
                valor_parcela=valor_parcela,
                qtd_parcela_saque_parcelado=qtd_parcela_saque_parcelado,
                valor_total_a_pagar=valor_total_a_pagar,
                id_cliente_cartao=id_cliente_cartao,
            )

            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.ANDAMENTO_SIMULACAO.value,
                created_by=user,
            )
            contrato.status = EnumContratoStatus.DIGITACAO
            contrato.save(update_fields=['status'])
            serializer = CriarContratoSaqueComplementarSerializer(contrato)
            return Response(serializer.data, status=HTTP_200_OK)

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao criar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )

    def preserve_2_decimal_positions(self, value: float) -> float:
        """
        Round a float with more than 2 decimal positions, to only 2
        decimal positions.
        """
        return round(value, 2)


class ConsultaIN100(GenericAPIView):
    """
    API utilizada para verificação se cliente ja fez aceite da IN100 para cartao beneficio.
    """

    serializer_class = CriarContratoSaqueComplementarSerializer

    def post(self, request):
        cpf_cliente = request.data['numero_cpf']
        nome_cliente = request.data['nome_cliente']
        telefone_cliente = request.data['telefone_cliente']
        produto = request.data['produto']

        aceite_in100 = None
        cliente = consulta_cliente(cpf_cliente)
        cliente.nome_cliente = nome_cliente
        cliente.telefone_celular = telefone_cliente
        cliente.save()

        context = {'id_cliente': cliente.id}
        try:
            aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
            data_hoje = date.today()

            if data_hoje <= aceite_in100.data_vencimento_aceite:
                context['in100_aceita'] = True
                context['url_formalizacao_curta'] = None

            elif (
                aceite_in100.data_vencimento_token is not None
                and data_hoje <= aceite_in100.data_vencimento_token
            ):
                context['in100_aceita'] = True
                context['url_formalizacao_curta'] = None
            else:
                context['in100_aceita'] = False
                url_formalizacao_curta = gerar_link_aceite_in100(cpf_cliente, produto)
                context['url_formalizacao_curta'] = url_formalizacao_curta

        except AceiteIN100.DoesNotExist:
            context['in100_aceita'] = False
            aceite_in100 = AceiteIN100()  # Creating an empty AceiteIN100 object

            url_formalizacao_curta = gerar_link_aceite_in100(cpf_cliente, produto)

            context['url_formalizacao_curta'] = url_formalizacao_curta

        serializer = ConsultaAceiteIN100Cartao(aceite_in100, context=context)
        return Response(serializer.data, status=HTTP_200_OK)


# criando uma api para assinar um termo sera nome cpf e assinatura, salvar no s3 e retornar a url
class Aceite_IN100(GenericAPIView):
    """
    API utilizada para assinar termo da IN100
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            id_cliente = request.data.get('id_cliente')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            ip_publico = request.data.get('ip_publico')
            produto = request.data.get('produto')

            context = {}

            # origin client

            if produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                if settings.ORIGIN_CLIENT == 'PINE':
                    context['url_aceite'] = aceite_in100_pine(
                        id_cliente, latitude, longitude, ip_publico, produto
                    )

                elif settings.ORIGIN_CLIENT == 'DIGIMAIS':
                    context['url_aceite'] = aceite_in100_digimais(
                        id_cliente=id_cliente,
                        latitude=latitude,
                        longitude=longitude,
                        ip_publico=ip_publico,
                        produto=produto,
                    )

                else:
                    context['url_aceite'] = aceite_in100(
                        id_cliente, latitude, longitude, ip_publico, produto
                    )

            return Response(context, status=HTTP_200_OK)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Houve um erro ao Assinar os Termos.'},
                status=HTTP_400_BAD_REQUEST,
            )


class AutorizacaoConsultaDigital(GenericAPIView):
    """
    API utilizada para autorizar a consulta da IN100 pelo Cliente.
    """

    def post(self, request):
        cpf_cliente = request.data['cpf_cliente']
        canal_autorizacao_digital = request.data['canal_autorizacao_digital']
        averbadora = request.data['averbadora']
        codigo_convenio = request.data['convenio']
        try:
            aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)

            if is_value_in_enum(canal_autorizacao_digital, EnumCanalAutorizacaoDigital):
                data_hoje = date.today()
                if (
                    aceite_in100.data_vencimento_token is not None
                    and data_hoje > aceite_in100.data_vencimento_token
                    or aceite_in100.data_vencimento_token is None
                ):
                    autorizacao = autorizacao_consulta_digital(
                        cpf_cliente,
                        canal_autorizacao_digital,
                        aceite_in100,
                        averbadora,
                        codigo_convenio,
                    )
                    return Response(autorizacao, status=HTTP_200_OK)
                else:
                    return Response(
                        {'Data do token do cliente ainda válida.'},
                        status=HTTP_200_OK,
                    )
            else:
                return Response(
                    {'Erro': 'Campo canal autorização digital incorreto.'},
                    status=HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            print(e)
            return Response(
                {
                    'Erro': 'Houve um erro ao realizar a autorização da consulta digital.'
                },
                status=HTTP_400_BAD_REQUEST,
            )


class ConsultaBeneficios(GenericAPIView):
    """
    API utilizada para consultar beneficios do cliente.
    """

    def post(self, request):
        cpf_cliente = request.data['cpf_cliente']
        averbadora = request.data['averbadora']
        try:
            aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
            tokenAutorizacao = aceite_in100.token_in100
            autorizacao = consulta_beneficio(cpf_cliente, tokenAutorizacao, averbadora)

            return Response(autorizacao, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'E02 - Não foi possível localizar o benefício do cliente.'},
                status=HTTP_400_BAD_REQUEST,
            )


class ConsultaMargemInss(GenericAPIView):
    """
    API utilizada para realizar a consulta margem IN100 do Cliente.
    """

    def post(self, request):
        cpf_cliente = request.data['cpf_cliente']
        numero_beneficio = request.data['numero_beneficio']
        averbadora = request.data['averbadora']
        codigo_convenio = request.data['convenio']
        try:
            aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
            tokenAutorizacao = aceite_in100.token_in100
            autorizacao, retorno_beneficio = consulta_margem_inss(
                cpf_cliente,
                tokenAutorizacao,
                averbadora,
                numero_beneficio,
            )
            tipo_credito_codigo = retorno_beneficio['tipoCredito']['codigo']
            if f'{tipo_credito_codigo}' == '1':
                retorno_beneficio['contaCorrente'] = ''

            convenio = Convenios.objects.get(
                pk=codigo_convenio, averbadora=averbadora, ativo=True
            )
            valid_data = filter_valid_margins(autorizacao, convenio, averbadora)
            # Chamando a função para criar e salvar o objeto DadosBeneficioIN100
            create_dados_beneficio(aceite_in100, retorno_beneficio)

            return Response(valid_data, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Houve um erro ao consultar os benefícios.'},
                status=HTTP_400_BAD_REQUEST,
            )


def create_dados_beneficio(aceite_in100_instance, retorno_beneficio):
    # Inicializando o objeto DadosBeneficioIN100
    dados_beneficio = DadosBeneficioIN100()

    # Atribuindo o objeto aceite_in100 passado como argumento
    dados_beneficio.aceite = aceite_in100_instance

    # Preenchendo campos do modelo com os dados do dicionário retorno_beneficio
    dados_beneficio.numero_beneficio = str(retorno_beneficio['numeroBeneficio'])
    dados_beneficio.cpf = str(retorno_beneficio['cpf'])
    dados_beneficio.nome_beneficiario = retorno_beneficio['nomeBeneficiario']
    dados_beneficio.codigo_situacao_beneficio = retorno_beneficio['situacaoBeneficio'][
        'codigo'
    ]
    dados_beneficio.descricao_situacao_beneficio = retorno_beneficio[
        'situacaoBeneficio'
    ]['descricao']
    dados_beneficio.codigo_especie_beneficio = retorno_beneficio['especieBeneficio'][
        'codigo'
    ]
    dados_beneficio.descricao_especie_beneficio = retorno_beneficio['especieBeneficio'][
        'descricao'
    ]
    dados_beneficio.concessao_judicial = retorno_beneficio['concessaoJudicial']
    dados_beneficio.uf_pagamento = retorno_beneficio['ufPagamento']
    dados_beneficio.codigo_tipo_credito = retorno_beneficio['tipoCredito']['codigo']
    dados_beneficio.descricao_tipo_credito = retorno_beneficio['tipoCredito'][
        'descricao'
    ]
    dados_beneficio.cbc_if_pagadora = retorno_beneficio['cbcIfPagadora']
    dados_beneficio.agencia_pagadora = retorno_beneficio['agenciaPagadora']
    try:
        if retorno_beneficio['contaCorrente']:
            dados_beneficio.conta_corrente = retorno_beneficio['contaCorrente'][-1]
        else:
            dados_beneficio.conta_corrente = ''
    except KeyError:
        dados_beneficio.conta_corrente = ''
    dados_beneficio.possui_representante_legal = retorno_beneficio[
        'possuiRepresentanteLegal'
    ]
    dados_beneficio.possui_procurador = retorno_beneficio['possuiProcurador']
    dados_beneficio.possui_entidade_representacao = retorno_beneficio[
        'possuiEntidadeRepresentacao'
    ]
    dados_beneficio.codigo_pensao_alimenticia = retorno_beneficio['pensaoAlimenticia'][
        'codigo'
    ]
    dados_beneficio.descricao_pensao_alimenticia = retorno_beneficio[
        'pensaoAlimenticia'
    ]['descricao']
    dados_beneficio.bloqueado_para_emprestimo = retorno_beneficio[
        'bloqueadoParaEmprestimo'
    ]
    dados_beneficio.margem_disponivel = retorno_beneficio['margemDisponivel']
    dados_beneficio.margem_disponivel_cartao = retorno_beneficio[
        'margemDisponivelCartao'
    ]
    dados_beneficio.valor_limite_cartao = retorno_beneficio['valorLimiteCartao']
    dados_beneficio.qtd_emprestimos_ativos_suspensos = retorno_beneficio[
        'qtdEmprestimosAtivosSuspensos'
    ]
    dados_beneficio.qtd_emprestimos_ativos = retorno_beneficio['qtdEmprestimosAtivos']
    dados_beneficio.qtd_emprestimos_suspensos = retorno_beneficio[
        'qtdEmprestimosSuspensos'
    ]
    dados_beneficio.qtd_emprestimos_refin = retorno_beneficio['qtdEmprestimosRefin']
    dados_beneficio.qtd_emprestimos_porta = retorno_beneficio['qtdEmprestimosPorta']
    # Considerando que a data no dicionário está em formato 'ddMMyyyy'
    dados_beneficio.data_consulta = datetime.strptime(
        retorno_beneficio['dataConsulta'], '%d%m%Y'
    ).date()
    dados_beneficio.elegivel_emprestimo = retorno_beneficio['elegivelEmprestimo']
    dados_beneficio.margem_disponivel_rcc = retorno_beneficio['margemDisponivelRCC']
    dados_beneficio.valor_limite_rcc = retorno_beneficio['valorLimiteRCC']
    dados_beneficio.valor_liquido = retorno_beneficio['valorLiquido']
    dados_beneficio.valor_comprometido = retorno_beneficio['valorComprometido']
    dados_beneficio.valor_maximo_comprometimento = retorno_beneficio[
        'valorMaximoComprometimento'
    ]

    # Salvando o objeto no banco de dados
    dados_beneficio.save()

    return dados_beneficio


def import_excel_view(request):
    if request.method != 'POST':
        return render(request, 'admin/averbacao_inss/registroinss_change_list.html')
    excel_file = request.FILES['excel_file']

    # Carrega o arquivo Excel usando openpyxl
    wb = openpyxl.load_workbook(excel_file)
    sheet = wb.active

    records = []
    for row in sheet.iter_rows(min_row=2, values_only=True):  # Ignorando o cabeçalho
        record = {
            'numeroBeneficio': row[0],
            'codigoSolicitante': row[1],
            'numeroContrato': str(row[2]),
            'valorSaldoLimiteCartao': row[3],
            'valorUtilizadoMesCartao': row[4],
            'valorDesconto': row[5],
            'valorIOF': row[6],
            'valorTaxaAnual': row[7],
            'valorCETAnual': row[8],
            'valorTaxaMensal': row[9],
            'valorCETMensal': row[10],
            'classificadorModalidade': row[11],
        }
        records.append(record)

    # Divide os registros em grupos de no máximo 100
    chunks = [records[i : i + 100] for i in range(0, len(records), 100)]

    for chunk in chunks:
        payload = {'inclusaoDescontoCartao': chunk}

        response = incluir_desconto_cartao(payload)
        # Convert the response text to a JSON object
        response_json = json.loads(response.text)
        # Format the JSON object as a string with indentation for readability
        formatted_json_string = json.dumps(response_json, indent=4)
        LogAverbacaoINSS.objects.create(response=formatted_json_string)

    messages.success(request, 'Excel importado com sucesso!')
    return redirect('/admin/cartao_beneficio/logaverbacaoinss/')


class CancelamentoPlano(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            id_cancellation = request.data.get('id_cancelamento')
            id_beneficio = request.data.get('id_beneficio')
            id_contrato = request.data.get('id_contrato')

            contract = Contrato.objects.get(id=id_contrato)
            cliente_cartao = ClienteCartaoBeneficio.objects.get(contrato=contract)
            cli_cartao = contract.cliente_cartao_contrato.get()
            cartao_beneficio = CartaoBeneficio.objects.get(contrato=contract)

            beneficios = BeneficiosContratado.objects.get(id=id_beneficio)
            pk_beneficio = beneficios.plano.pk

            for plano in contract.contrato_planos_contratados.filter():
                plano = plano.plano
                if plano.pk == pk_beneficio:
                    if beneficios.status != 4:
                        if plano.seguradora.nome == EnumSeguradoras.GENERALI:
                            inicio_vigencia = contract.criado_em
                            hoje = datetime.now(timezone.utc).astimezone(
                                inicio_vigencia.tzinfo
                            )
                            diferenca = hoje - inicio_vigencia

                            data_venda_ajuste = contract.criado_em
                            data_venda_ajuste += relativedelta(
                                months=plano.quantidade_parcelas
                            )
                            data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')
                            data_fim_vigencia = datetime.strptime(
                                data_fim_vigencia, '%Y%m%d'
                            ).date()

                            if diferenca.days + 1 > 7:
                                if plano.tipo_plano in (
                                    EnumTipoPlano.OURO,
                                    EnumTipoPlano.DIAMANTE,
                                ):
                                    __, __, cf = calcular_cf(
                                        plano,
                                        contract,
                                        diferenca.days,
                                        inicio_vigencia,
                                        data_fim_vigencia,
                                        beneficios,
                                    )
                                    save_cf = cf
                                    cf = cf
                                    operacao_sequencial, cnpj = check_plano(plano)

                                    maior_sequencial = (
                                        get_maior_sequencial(operacao_sequencial)
                                        if get_maior_sequencial(operacao_sequencial) > 0
                                        else 1
                                    )

                                    maior_sequencial_nome = f'{maior_sequencial}'.rjust(
                                        6, '0'
                                    )
                                    today = datetime.now()
                                    today_str = today.strftime('%Y%m%d')

                                    nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

                                    id_seq = f'{cliente_cartao.id_conta_dock}'
                                    nova_id_seq = id_seq
                                    identificacao_seguro = (
                                        plano.codigo_sucursal
                                        + plano.codigo_ramo
                                        + plano.codigo_operacao
                                        + plano.codigo_plano
                                    )

                                    if len(identificacao_seguro + nova_id_seq) < 18:
                                        zeros_a_adicionar = 18 - len(
                                            identificacao_seguro + nova_id_seq
                                        )
                                        nova_id_seq = (
                                            '0' * zeros_a_adicionar + nova_id_seq
                                        )
                                    try:
                                        identificacao_nova = (
                                            identificacao_seguro + nova_id_seq
                                        )
                                    except Exception:
                                        identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
                                            :18
                                        ]

                                    with tempfile.TemporaryDirectory() as temp_dir:
                                        local_path = os.path.join(temp_dir, nomeArquivo)

                                        # Baixe o arquivo do S3 se ele existir
                                        file_exists_in_s3 = True
                                        s3 = boto3.client(
                                            's3',
                                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                        )
                                        try:
                                            s3.download_file(
                                                settings.BUCKET_SEGUROS,
                                                nomeArquivo,
                                                local_path,
                                            )
                                        except Exception as e:
                                            print(
                                                'Arquivo ainda nao existente na s3, iremos cria-lo',
                                                e,
                                            )
                                            file_exists_in_s3 = False

                                        save_plano = plano
                                        produto = f'{plano.codigo_produto}'.ljust(
                                            5, ' '
                                        )
                                        apolice = f'{plano.apolice}'.rjust(10, '0')
                                        codigo_operacao = plano.codigo_operacao
                                        plano = f'{plano.codigo_plano}'.ljust(10, ' ')
                                        id_cancellation = f'{id_cancellation}'.ljust(
                                            4, ' '
                                        )
                                        cf = f'{cf}'.replace('.', '').replace(',', '')
                                        cnpj = f'{cnpj}'.rjust(15, '0')
                                        sequencial_registro = 1
                                        sequencial_do_registro = (
                                            f'{sequencial_registro}'.rjust(6, '0')
                                        )
                                        with open(local_path, 'a') as destino:
                                            if not file_exists_in_s3:
                                                logger.info(
                                                    'iniciou o processo de inclusão do header'
                                                )
                                                write_initial_content(
                                                    destino,
                                                    produto,
                                                    apolice,
                                                    today_str,
                                                    maior_sequencial_nome,
                                                    codigo_operacao,
                                                )
                                        with open(local_path, 'a') as destino:
                                            remove_first_line_starting_with(
                                                start_text='9', local_path=destino
                                            )
                                            dado_retorno, _ = check_data_in_range(
                                                start_index=1295,
                                                end_index=1300,
                                                local_path=destino,
                                            )
                                            if dado_retorno:
                                                sequencial_do_registro = (
                                                    int(dado_retorno) + 1
                                                )
                                                sequencial_do_registro = (
                                                    f'{sequencial_do_registro}'.rjust(
                                                        6, '0'
                                                    )
                                                )

                                            write_cancelamento(
                                                destino,
                                                produto,
                                                apolice,
                                                plano,
                                                cnpj,
                                                f'{identificacao_nova}'.rjust(20, ' '),
                                                datetime.now().strftime('%Y%m%d'),
                                                id_cancellation,
                                                f'{cf}'.rjust(15, '0'),
                                                sequencial_do_registro,
                                            )
                                        with open(local_path, 'a') as destino:
                                            dado_retorno, _ = check_data_in_range(
                                                start_index=1295,
                                                end_index=1300,
                                                local_path=destino,
                                            )
                                            if dado_retorno:
                                                sequencial_do_registro = (
                                                    int(dado_retorno) + 1
                                                )
                                                sequencial_do_registro = (
                                                    f'{sequencial_do_registro}'.rjust(
                                                        6, '0'
                                                    )
                                                )
                                            count = count_reg(destino) + 2
                                            count = f'{count}'.rjust(6, '0')
                                            write_trailer(
                                                destino, count, sequencial_do_registro
                                            )
                                        with open(local_path, 'a') as destino:
                                            ajustar_posicoes(destino)

                                        s3.upload_file(
                                            local_path,
                                            settings.BUCKET_SEGUROS,
                                            nomeArquivo,
                                        )
                                        beneficios.status = 4
                                        beneficios.save()
                                        solicitar_cobranca_operacoes(
                                            contract,
                                            save_plano,
                                            cartao_beneficio,
                                            cli_cartao,
                                        )
                                        InformativoCancelamentoPlano.objects.create(
                                            motivo=id_cancellation,
                                            valor_estorno=save_cf,
                                            contrato=contract,
                                            cliente=contract.cliente,
                                        )
                                        return Response(
                                            {'msg': 'Arquivo criado com sucesso.'},
                                            status=HTTP_200_OK,
                                        )
                                else:
                                    cf = 0
                                    save_cf = cf
                                    cf = f'{cf:.2f}'

                                    operacao_sequencial, cnpj = check_plano(plano)

                                    maior_sequencial = (
                                        get_maior_sequencial(operacao_sequencial)
                                        if get_maior_sequencial(operacao_sequencial) > 0
                                        else 1
                                    )
                                    maior_sequencial_nome = f'{maior_sequencial}'.rjust(
                                        6, '0'
                                    )
                                    today = datetime.now()
                                    today_str = today.strftime('%Y%m%d')

                                    nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

                                    id_seq = f'{cliente_cartao.id_conta_dock}'
                                    nova_id_seq = id_seq
                                    identificacao_seguro = (
                                        plano.codigo_sucursal
                                        + plano.codigo_ramo
                                        + plano.codigo_operacao
                                        + plano.codigo_plano
                                    )

                                    if len(identificacao_seguro + nova_id_seq) < 18:
                                        zeros_a_adicionar = 18 - len(
                                            identificacao_seguro + nova_id_seq
                                        )
                                        nova_id_seq = (
                                            '0' * zeros_a_adicionar + nova_id_seq
                                        )
                                    try:
                                        identificacao_nova = (
                                            identificacao_seguro + nova_id_seq
                                        )
                                    except Exception:
                                        identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
                                            :18
                                        ]

                                    with tempfile.TemporaryDirectory() as temp_dir:
                                        local_path = os.path.join(temp_dir, nomeArquivo)

                                        # Baixe o arquivo do S3 se ele existir
                                        file_exists_in_s3 = True
                                        s3 = boto3.client(
                                            's3',
                                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                        )
                                        try:
                                            s3.download_file(
                                                settings.BUCKET_SEGUROS,
                                                nomeArquivo,
                                                local_path,
                                            )
                                        except Exception as e:
                                            print(
                                                'Arquivo ainda nao existente na s3, iremos cria-lo',
                                                e,
                                            )
                                            file_exists_in_s3 = False

                                        save_plano = plano
                                        produto = f'{plano.codigo_produto}'.ljust(
                                            5, ' '
                                        )
                                        apolice = f'{plano.apolice}'.rjust(10, '0')
                                        codigo_operacao = plano.codigo_operacao
                                        plano = f'{plano.codigo_plano}'.ljust(10, ' ')
                                        id_cancellation = f'{id_cancellation}'.ljust(
                                            4, ' '
                                        )
                                        cf = f'{cf}'.replace('.', '').replace(',', '')
                                        cnpj = f'{cnpj}'.rjust(15, '0')
                                        sequencial_registro = 1
                                        sequencial_do_registro = (
                                            f'{sequencial_registro}'.rjust(6, '0')
                                        )
                                        with open(local_path, 'a') as destino:
                                            if not file_exists_in_s3:
                                                logger.info(
                                                    'iniciou o processo de inclusão do header'
                                                )
                                                write_initial_content(
                                                    destino,
                                                    produto,
                                                    apolice,
                                                    today_str,
                                                    maior_sequencial_nome,
                                                    codigo_operacao,
                                                )
                                        with open(local_path, 'a') as destino:
                                            remove_first_line_starting_with(
                                                start_text='9', local_path=destino
                                            )

                                            dado_retorno, _ = check_data_in_range(
                                                start_index=1295,
                                                end_index=1300,
                                                local_path=destino,
                                            )
                                            if dado_retorno:
                                                sequencial_do_registro = (
                                                    int(dado_retorno) + 1
                                                )
                                                sequencial_do_registro = (
                                                    f'{sequencial_do_registro}'.rjust(
                                                        6, '0'
                                                    )
                                                )

                                            write_cancelamento(
                                                destino,
                                                produto,
                                                apolice,
                                                plano,
                                                cnpj,
                                                f'{identificacao_nova}'.rjust(20, ' '),
                                                datetime.now().strftime('%Y%m%d'),
                                                id_cancellation,
                                                f'{cf}'.rjust(15, '0'),
                                                sequencial_do_registro,
                                            )
                                            data_venda = datetime.strftime(
                                                contract.criado_em, '%Y%m%d'
                                            )
                                            data_venda_ajuste = datetime.strptime(
                                                data_venda, '%Y%m%d'
                                            )
                                            data_venda_ajuste += relativedelta(
                                                months=save_plano.quantidade_parcelas
                                            )
                                            data_fim_vigencia = (
                                                data_venda_ajuste.strftime('%d/%m/%Y')
                                            )
                                        with open(local_path, 'a') as destino:
                                            dado_retorno, _ = check_data_in_range(
                                                start_index=1295,
                                                end_index=1300,
                                                local_path=destino,
                                            )
                                            if dado_retorno:
                                                sequencial_do_registro = (
                                                    int(dado_retorno) + 1
                                                )
                                                sequencial_do_registro = (
                                                    f'{sequencial_do_registro}'.rjust(
                                                        6, '0'
                                                    )
                                                )
                                            count = count_reg(destino) + 2
                                            count = f'{count}'.rjust(6, '0')
                                            write_trailer(
                                                destino, count, sequencial_do_registro
                                            )
                                        with open(local_path, 'a') as destino:
                                            ajustar_posicoes(destino)

                                        s3.upload_file(
                                            local_path,
                                            settings.BUCKET_SEGUROS,
                                            nomeArquivo,
                                        )
                                        beneficios.status = 4
                                        beneficios.save()
                                        InformativoCancelamentoPlano.objects.create(
                                            motivo=id_cancellation,
                                            valor_estorno=save_cf,
                                            contrato=contract,
                                            cliente=contract.cliente,
                                        )
                                        return Response(
                                            {'msg': 'Arquivo criado com sucesso.'},
                                            status=HTTP_200_OK,
                                        )
                            else:
                                cf = float(beneficios.premio_bruto)
                                cf = f'{cf:.2f}'
                                save_cf = cf

                                operacao_sequencial, cnpj = check_plano(plano)

                                maior_sequencial = (
                                    get_maior_sequencial(operacao_sequencial)
                                    if get_maior_sequencial(operacao_sequencial) > 0
                                    else 1
                                )
                                maior_sequencial_nome = f'{maior_sequencial}'.rjust(
                                    6, '0'
                                )
                                today = datetime.now()
                                today_str = today.strftime('%Y%m%d')

                                nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

                                id_seq = f'{cliente_cartao.id_conta_dock}'
                                nova_id_seq = id_seq
                                identificacao_seguro = (
                                    plano.codigo_sucursal
                                    + plano.codigo_ramo
                                    + plano.codigo_operacao
                                    + plano.codigo_plano
                                )

                                if len(identificacao_seguro + nova_id_seq) < 18:
                                    zeros_a_adicionar = 18 - len(
                                        identificacao_seguro + nova_id_seq
                                    )
                                    nova_id_seq = '0' * zeros_a_adicionar + nova_id_seq
                                try:
                                    identificacao_nova = (
                                        identificacao_seguro + nova_id_seq
                                    )
                                except Exception:
                                    identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
                                        :18
                                    ]

                                with tempfile.TemporaryDirectory() as temp_dir:
                                    local_path = os.path.join(temp_dir, nomeArquivo)

                                    # Baixe o arquivo do S3 se ele existir
                                    file_exists_in_s3 = True
                                    s3 = boto3.client(
                                        's3',
                                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                    )
                                    try:
                                        s3.download_file(
                                            settings.BUCKET_SEGUROS,
                                            nomeArquivo,
                                            local_path,
                                        )
                                    except Exception as e:
                                        print(
                                            'Arquivo ainda nao existente na s3, iremos cria-lo',
                                            e,
                                        )
                                        file_exists_in_s3 = False
                                    save_plano = plano
                                    produto = f'{plano.codigo_produto}'.ljust(5, ' ')
                                    apolice = f'{plano.apolice}'.rjust(10, '0')
                                    codigo_operacao = plano.codigo_operacao
                                    plano = f'{plano.codigo_plano}'.ljust(10, ' ')
                                    id_cancellation = f'{id_cancellation}'.ljust(4, ' ')
                                    cf = f'{cf}'.replace('.', '').replace(',', '')
                                    cnpj = f'{cnpj}'.rjust(15, '0')
                                    sequencial_registro = 1
                                    sequencial_do_registro = (
                                        f'{sequencial_registro}'.rjust(6, '0')
                                    )
                                    with open(local_path, 'a') as destino:
                                        if not file_exists_in_s3:
                                            logger.info(
                                                'iniciou o processo de inclusão do header'
                                            )
                                            write_initial_content(
                                                destino,
                                                produto,
                                                apolice,
                                                today_str,
                                                maior_sequencial_nome,
                                                codigo_operacao,
                                            )
                                    with open(local_path, 'a') as destino:
                                        remove_first_line_starting_with(
                                            start_text='9', local_path=destino
                                        )
                                        dado_retorno, _ = check_data_in_range(
                                            start_index=1295,
                                            end_index=1300,
                                            local_path=destino,
                                        )
                                        if dado_retorno:
                                            sequencial_do_registro = (
                                                int(dado_retorno) + 1
                                            )
                                            sequencial_do_registro = (
                                                f'{sequencial_do_registro}'.rjust(
                                                    6, '0'
                                                )
                                            )

                                        write_cancelamento(
                                            destino,
                                            produto,
                                            apolice,
                                            plano,
                                            cnpj,
                                            f'{identificacao_nova}'.rjust(20, ' '),
                                            datetime.now().strftime('%Y%m%d'),
                                            id_cancellation,
                                            f'{cf}'.rjust(15, '0'),
                                            sequencial_do_registro,
                                        )
                                        data_venda = datetime.strftime(
                                            contract.criado_em, '%Y%m%d'
                                        )
                                        data_venda_ajuste = datetime.strptime(
                                            data_venda, '%Y%m%d'
                                        )
                                        data_venda_ajuste += relativedelta(
                                            months=save_plano.quantidade_parcelas
                                        )
                                        data_fim_vigencia = data_venda_ajuste.strftime(
                                            '%d/%m/%Y'
                                        )
                                    with open(local_path, 'a') as destino:
                                        dado_retorno, _ = check_data_in_range(
                                            start_index=1295,
                                            end_index=1300,
                                            local_path=destino,
                                        )
                                        if dado_retorno:
                                            sequencial_do_registro = (
                                                int(dado_retorno) + 1
                                            )
                                            sequencial_do_registro = (
                                                f'{sequencial_do_registro}'.rjust(
                                                    6, '0'
                                                )
                                            )
                                        count = count_reg(destino) + 2
                                        count = f'{count}'.rjust(6, '0')
                                        write_trailer(
                                            destino, count, sequencial_do_registro
                                        )
                                    with open(local_path, 'a') as destino:
                                        ajustar_posicoes(destino)

                                    s3.upload_file(
                                        local_path, settings.BUCKET_SEGUROS, nomeArquivo
                                    )
                                    beneficios.status = 4
                                    beneficios.save()

                                    if save_plano.tipo_plano in (
                                        EnumTipoPlano.OURO,
                                        EnumTipoPlano.DIAMANTE,
                                    ):
                                        solicitar_cobranca_operacoes(
                                            contract,
                                            save_plano,
                                            cartao_beneficio,
                                            cli_cartao,
                                        )
                                    InformativoCancelamentoPlano.objects.create(
                                        motivo=id_cancellation,
                                        valor_estorno=save_cf,
                                        contrato=contract,
                                        cliente=contract.cliente,
                                    )
                                    return Response(
                                        {'msg': 'Arquivo criado com sucesso.'},
                                        status=HTTP_200_OK,
                                    )
                        return Response(
                            {'Erro': 'Plano inexistente.'}, status=HTTP_404_NOT_FOUND
                        )
                    return Response(
                        {'Erro': 'Plano já foi cancelado.'}, status=HTTP_400_BAD_REQUEST
                    )
            return Response(
                {'Erro': 'Cliente não tem plano ativo'}, status=HTTP_404_NOT_FOUND
            )
        except Contrato.DoesNotExist:
            return Response(
                {'Erro': 'Contrato inexistente.'}, status=HTTP_404_NOT_FOUND
            )
        except ClienteCartaoBeneficio.DoesNotExist:
            return Response(
                {'Erro': 'Cartão de benefício inexistente.'}, status=HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({'Erro': str(e)}, status=HTTP_400_BAD_REQUEST)


class ArrecadacaoPlano(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            id_beneficio = request.data.get('id_beneficio')
            id_contrato = request.data.get('id_contrato')

            contract = Contrato.objects.get(id=id_contrato)
            cliente_cartao = ClienteCartaoBeneficio.objects.get(contrato=contract)
            beneficios = BeneficiosContratado.objects.get(id=id_beneficio)
            pk_beneficio = beneficios.plano.pk

            for plano in contract.contrato_planos_contratados.filter():
                plano = plano.plano
                if plano.pk == pk_beneficio:
                    if beneficios.status != 4:
                        if plano.tipo_plano == EnumTipoPlano.PRATA:
                            cf = float(beneficios.premio_bruto)
                            cf = f'{cf:.2f}'
                            operacao_sequencial, cnpj = check_plano(plano)
                            maior_sequencial = (
                                get_maior_sequencial(operacao_sequencial)
                                if get_maior_sequencial(operacao_sequencial) > 0
                                else 1
                            )

                            maior_sequencial_nome = f'{maior_sequencial}'.rjust(6, '0')
                            today = datetime.now()
                            today_str = today.strftime('%Y%m%d')

                            nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

                            id_seq = f'{cliente_cartao.id_conta_dock}'
                            nova_id_seq = id_seq
                            identificacao_seguro = (
                                plano.codigo_sucursal
                                + plano.codigo_ramo
                                + plano.codigo_operacao
                                + plano.codigo_plano
                            )

                            if len(identificacao_seguro + nova_id_seq) < 18:
                                zeros_a_adicionar = 18 - len(
                                    identificacao_seguro + nova_id_seq
                                )
                                nova_id_seq = '0' * zeros_a_adicionar + nova_id_seq
                            try:
                                identificacao_nova = identificacao_seguro + nova_id_seq
                            except Exception:
                                identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
                                    :18
                                ]

                            with tempfile.TemporaryDirectory() as temp_dir:
                                data_venda = datetime.strftime(
                                    contract.criado_em, '%Y%m%d'
                                )
                                data_venda_ajuste = datetime.strptime(
                                    data_venda, '%Y%m%d'
                                )
                                data_venda_ajuste += relativedelta(
                                    months=plano.quantidade_parcelas
                                )
                                data_fim_vigencia = data_venda_ajuste.strftime(
                                    '%d/%m/%Y'
                                )
                                qtd = (
                                    beneficios.validade
                                    if beneficios.validade is not None
                                    else '24'
                                    if plano.tipo_plano == EnumTipoPlano.PRATA
                                    else '01'
                                )
                                qtd_parcela = identificar_parcela(
                                    f'{data_venda}',
                                    f'{qtd}',
                                    f'{data_fim_vigencia}',
                                )
                                plano_codigo = plano.codigo_plano
                                data_c = contract.criado_em.strftime('%Y%m%d')
                                produto = f'{plano.codigo_produto}'.ljust(5, ' ')
                                apolice = f'{plano.apolice}'.rjust(10, '0')
                                codigo_operacao = plano.codigo_operacao
                                plano = f'{plano.codigo_plano}'.ljust(10, ' ')
                                cf = f'{cf}'.replace('.', '').replace(',', '')
                                cnpj = f'{cnpj}'.rjust(15, '0')
                                sequencial_registro = 1
                                sequencial_do_registro = f'{sequencial_registro}'.rjust(
                                    6, '0'
                                )
                                local_path = os.path.join(temp_dir, nomeArquivo)

                                # Baixe o arquivo do S3 se ele existir
                                file_exists_in_s3 = True
                                s3 = boto3.client(
                                    's3',
                                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                )
                                try:
                                    s3.download_file(
                                        settings.BUCKET_SEGUROS,
                                        nomeArquivo,
                                        local_path,
                                    )
                                except Exception as e:
                                    print(
                                        'Arquivo ainda nao existente na s3, iremos cria-lo',
                                        e,
                                    )
                                    file_exists_in_s3 = False

                                with open(local_path, 'a') as destino:
                                    if not file_exists_in_s3:
                                        logger.info(
                                            'iniciou o processo de inclusão do header'
                                        )
                                        write_initial_content(
                                            destino,
                                            produto,
                                            apolice,
                                            today_str,
                                            maior_sequencial_nome,
                                            codigo_operacao,
                                        )
                                with open(local_path, 'a') as destino:
                                    remove_first_line_starting_with(
                                        start_text='9', local_path=destino
                                    )
                                    dado_retorno, _ = check_data_in_range(
                                        start_index=1295,
                                        end_index=1300,
                                        local_path=destino,
                                    )
                                    if dado_retorno:
                                        sequencial_do_registro = int(dado_retorno) + 1
                                        sequencial_do_registro = (
                                            f'{sequencial_do_registro}'.rjust(6, '0')
                                        )

                                    escrever_arrecadacao(
                                        destino,
                                        produto,
                                        apolice,
                                        plano_codigo,
                                        f'{identificacao_nova}'.rjust(20, ' '),
                                        f'{qtd_parcela}'.ljust(3, ' '),
                                        data_c,
                                        f'{cf}'.rjust(15, '0'),
                                        f'{cnpj}'.rjust(15, '0'),
                                        sequencial_do_registro,
                                        motivo='A',
                                    )
                                    beneficios.qtd_arrecadacao = (
                                        1
                                        if beneficios.qtd_arrecadacao is None
                                        else int(beneficios.qtd_arrecadacao) + 1
                                    )
                                    beneficios.save()
                                with open(local_path, 'a') as destino:
                                    dado_retorno, _ = check_data_in_range(
                                        start_index=1295,
                                        end_index=1300,
                                        local_path=destino,
                                    )
                                    if dado_retorno:
                                        sequencial_do_registro = int(dado_retorno) + 1
                                        sequencial_do_registro = (
                                            f'{sequencial_do_registro}'.rjust(6, '0')
                                        )
                                    count = count_reg(destino) + 2
                                    count = f'{count}'.rjust(6, '0')
                                    write_trailer(
                                        destino, count, sequencial_do_registro
                                    )
                                with open(local_path, 'a') as destino:
                                    ajustar_posicoes(destino)

                                s3.upload_file(
                                    local_path, settings.BUCKET_SEGUROS, nomeArquivo
                                )
                                return Response(
                                    {'msg': 'Arquivo criado com sucesso.'},
                                    status=HTTP_200_OK,
                                )
                        return Response(
                            {'Erro': 'Plano não liberado para arrecadação.'},
                            status=HTTP_404_NOT_FOUND,
                        )
                    return Response(
                        {'Erro': 'Plano foi cancelado.'}, status=HTTP_400_BAD_REQUEST
                    )
            return Response(
                {'Erro': 'Cliente não tem plano ativo'}, status=HTTP_404_NOT_FOUND
            )
        except Contrato.DoesNotExist:
            return Response(
                {'Erro': 'Contrato inexistente.'}, status=HTTP_404_NOT_FOUND
            )
        except ClienteCartaoBeneficio.DoesNotExist:
            return Response(
                {'Erro': 'Cartão de benefício inexistente.'}, status=HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(e.__traceback__.tb_lineno)
            return Response({'Erro': str(e)}, status=HTTP_400_BAD_REQUEST)
