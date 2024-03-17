import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Union

import newrelic.agent
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from contract.constants import (
    STATUS_REPROVADOS,
    EnumContratoStatus,
    EnumTipoContrato,
    EnumTipoProduto,
    ProductTypeEnum,
    EnumEscolaridade,
)
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
    SaqueComplementar,
)

from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import Convenios
from contract.products.cartao_beneficio.models.planos import Planos, PlanosContrato
from contract.products.cartao_beneficio.termos import (
    get_dados_contrato,
    get_dados_contrato_saque_complementar,
)
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.termos import assinatura_termo_in100
from contract.products.portabilidade.views import status_envio_link_portabilidade
from contract.products.portabilidade_refin.handle_response import HandleQitechResponse
from contract.serializers import (
    ContratoKPISerializer,
    ContratoSerializer,
    CriarContratoPortabilidadeSerializer,
    CriarContratoSerializer,
    DadosIN100Serializer,
    SimulacaoPortabilidadeSerializer,
    StatusContratoPortabilidadeSerializer,
)
from contract.services.persistance.client import create_client_contract_witnesses
from contract.services.validators.in100 import validate_client_installments_number
from contract.services.validators.minimum_value import MinimumValueValidator
from contract.services.validators.products import MaxContractByCPFValidator
from contract.utils import atualizar_status_contratos
from core import settings
from core.common.enums import EnvironmentEnum
from core.models import Cliente, ParametrosBackoffice
from core.models.cliente import ClienteCartaoBeneficio
from core.models.parametro_produto import ParametrosProduto
from core.tasks import (
    insere_proposta_margem_livre_financeira_hub,
    validar_contrato_assync,
)
from django.db.models import Sum, F, Case, When, Value, FloatField
from django.db.models.functions import Coalesce
from core.tasks.insert_portability_proposal import insert_portability_proposal
from core.utils import consulta_cliente, generate_short_url
from custom_auth.models import UserProfile
from handlers.portabilidade_in100 import consulta_beneficio_in100_portabilidade
from handlers.simulacao_portabilidade import simulacao_portabilidade_financeira_hub
from handlers.webhook_qitech import salvando_retorno_IN100_contrato
from handlers.zenvia_sms import zenvia_sms

STATUS_APROVADOS = [
    ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
    ContractStatus.INT_AGUARDA_AVERBACAO.value,
    ContractStatus.INT_AGUARDANDO_PAGO_QITECH.value,
    ContractStatus.INT_FINALIZADO.value,
    ContractStatus.AGUARDANDO_AVERBACAO_REFIN.value,
    ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value,
    ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
]
STATUS_PENDENTE = [
    ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value,
    ContractStatus.AGUARDANDO_IN100_RECALCULO.value,
    ContractStatus.RETORNO_IN100_RECALCULO_RECEBIDO.value,
    ContractStatus.SALDO_RETORNADO.value,
]

# TODO Quando possivel realizar a refatoração das API's de contratos criando uma unica API ultilizando: post, put, get

logger = logging.getLogger(__name__)


class CriarContrato(GenericAPIView):
    """
    API utilizada para a criação de um contrato durante a jornada de originação.
    """

    serializer_class = CriarContratoSerializer

    def post(self, request):
        try:
            data = request.data
            tipo_produto: int = int(data.get('tipo_produto'))
            cpf_cliente: str = data.get('numero_cpf')

            client_id: int = data.get('id_cliente')
            client = Cliente.objects.filter(nu_cpf=cpf_cliente).first()

            proposals: list[dict[str, any]] = data.get(
                'portabilidade_refinanciamento', []
            )

            # Check the client number of contracts to create free margin
            # and protability + refinancing
            MaxContractByCPFValidator(
                client_id=client_id or client.id,
                product_type=ProductTypeEnum(tipo_produto),
                proposals_amount=len(proposals) or 1,
                numero_beneficio=data.get('numero_beneficio'),
            ).check_active_contracts()

            if tipo_produto not in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            ):
                # validate contract minimum value
                MinimumValueValidator(data).validate()

            if tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                return self._create_port_refin(request=request)
            if tipo_produto == EnumTipoProduto.PORTABILIDADE:
                return self._create_port(request=request)
            try:
                dados_cliente = self._validar_contratos_cliente(
                    cpf_cliente=cpf_cliente, tipo_produto=tipo_produto
                )
                user = get_object_or_404(
                    UserProfile, identifier=request.user.identifier
                )
                return self._criar_contrato(
                    user=user, data=data, tipo_produto=tipo_produto, **dados_cliente
                )
            except ValueError as e:
                raise ValidationError(
                    detail={'Erro': str(e)}, code=HTTP_400_BAD_REQUEST
                ) from e
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception(
                'Something wrong when creating free margin or portability contracts'
            )
            raise ValidationError(
                detail={'Erro': 'Confira os parametros do sistema e tente novamente.'},
                code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

    def _validar_contratos_cliente(self, cpf_cliente, tipo_produto):
        dados_cliente = {'cliente': consulta_cliente(cpf_cliente)}
        parametros_backoffice = ParametrosBackoffice.objects.get(
            tipoProduto=tipo_produto
        )
        dados_cliente['quantidade_contratos_por_cliente'] = (
            parametros_backoffice.quantidade_contratos_por_cliente
        )

        tokens_contratos_uuids = Contrato.objects.filter(
            cliente=dados_cliente['cliente'],
            tipo_produto=tipo_produto,
        ).values_list('token_contrato', flat=True)
        dados_cliente['tokens_contratos'] = [str(o) for o in tokens_contratos_uuids]

        return dados_cliente

    def _atualizar_cliente(self, cliente, data):
        cliente.save()

        if int(data['tipo_produto']) in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            convenio = Convenios.objects.get(id=data.get('convenio'))
            cliente_cartao, _ = ClienteCartaoBeneficio.objects.get_or_create(
                pk=int(data.get('id_cliente_cartao'))
            )
            cliente_cartao.convenio = convenio
            cliente_cartao.margem_atual = data.get('margem_atual')

            cliente_cartao.save()

    def _cria_contrato_produto(self, tipo_produto, cliente, user, data):
        contrato = None

        if data.get('token_contrato'):
            contrato = Contrato.objects.get(token_contrato=data.get('token_contrato'))

        if not contrato:
            contrato = Contrato.objects.create(
                cliente=cliente,
                tipo_produto=tipo_produto,
                cd_contrato_tipo=int(data.get('tipo_contrato')),
                token_envelope=data.get('token_envelope'),
                created_by=user,
                corban=user.corban,
                corban_photo=user.corban.corban_name,
                created_by_photo=user.name,
                numero_beneficio=data.get('numero_beneficio'),
                contrato_cross_sell=data.get('contrato_cross_sell', False),
            )
        else:
            contrato.cliente = cliente
            contrato.tipo_produto = tipo_produto
            contrato.cd_contrato_tipo = int(data.get('tipo_contrato'))
            contrato.token_envelope = data.get('token_envelope')
            contrato.created_by = user
            contrato.corban = user.corban
            contrato.corban_photo = user.corban.corban_name
            contrato.created_by_photo = user.name
            contrato.numero_beneficio = data.get('numero_beneficio')
            contrato.contrato_cross_sell = data.get('contrato_cross_sell', False)

        if int(tipo_produto) in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            self._atualizar_dados_contrato(contrato, data, tipo_produto)
            self._create_card_product(contract=contrato, data=data)

        elif int(tipo_produto) in [
            EnumTipoProduto.MARGEM_LIVRE,
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_CORBAN,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
        ]:
            self._create_inss_free_margin_product(
                contract=contrato, data=data, user=user
            )
            self._atualizar_dados_contrato(contrato, data, tipo_produto)

            if cliente.escolaridade == EnumEscolaridade.ANALFABETO:
                contrato.rogado_id = data.get('id_rogado')
                contrato.save(update_fields=['rogado_id'])

                create_client_contract_witnesses(
                    client=cliente,
                    witnesses_payload=data.get('testemunhas', []),
                    contract_ids=[contrato.id],
                )

        return contrato

    def _create_card_product(self, contract, data):
        convenio = Convenios.objects.get(id=data.get('convenio'))

        cliente_cartao = ClienteCartaoBeneficio.objects.get(
            pk=int(data.get('id_cliente_cartao'))
        )
        cliente_cartao.contrato = contract
        cliente_cartao.tipo_margem = data.get('tipo_margem')
        cliente_cartao.limite_pre_aprovado = data.get('limite_pre_aprovado_compra')
        cliente_cartao.limite_pre_aprovado_saque = data.get('limite_pre_aprovado_saque')
        cliente_cartao.limite_pre_aprovado_compra = data.get(
            'limite_pre_aprovado_compra'
        )
        cliente_cartao.instituidor = data.get('instituidor')
        cliente_cartao.convenio_siape = data.get('convenio_siape')
        cliente_cartao.classificacao_siape = data.get('classificacao_siape')
        cliente_cartao.tipo_vinculo_siape = data.get('tipo_vinculo')
        cliente_cartao.senha_portal = data.get('senha_servidor')

        cliente_cartao.save()

        CartaoBeneficio.objects.create(
            contrato=contract,
            status=ContractStatus.FORMALIZACAO_CLIENTE.value,
            folha=data.get('folha'),
            convenio=convenio,
            senha_servidor=data.get('senha_servidor'),
            possui_saque=data.get('possui_saque'),
            saque_parcelado=data.get('saque_parcelado'),
            valor_disponivel_saque=data.get('valor_disponivel_saque'),
            valor_financiado=data.get('valor_financiado'),
            valor_saque=data.get('valor_saque'),
            verba=data.get('verba'),
            qtd_parcela_saque_parcelado=data.get('qtd_parcela_saque_parcelado'),
            valor_parcela=data.get('valor_parcela'),
            valor_total_a_pagar=data.get('valor_total_a_pagar'),
            tipo_margem=data.get('tipo_margem'),
            folha_compra=data.get('folha_compra'),
            verba_compra=data.get('verba_compra'),
            folha_saque=data.get('folha_saque'),
            verba_saque=data.get('verba_saque'),
            instituidor=data.get('instituidor'),
            convenio_siape=data.get('convenio_siape'),
            classificacao_siape=data.get('classificacao_siape'),
            tipo_vinculo_siape=data.get('tipo_vinculo'),
        )

    @staticmethod
    def _create_inss_free_margin_product(contract, data, user):
        margem_livre, _ = MargemLivre.objects.update_or_create(
            contrato=contract,
            status=ContractStatus.AGUARDA_ENVIO_LINK.value,
        )
        margem_livre.dt_vencimento_primeira_parcela = data[
            'dt_vencimento_primeira_parcela'
        ]
        margem_livre.dt_vencimento_ultima_parcela = data['dt_vencimento_ultima_parcela']
        margem_livre.vr_contrato = data['vr_contrato']
        margem_livre.vr_liberado_cliente = data['vr_liberado_cliente']
        margem_livre.qtd_parcelas = data['qt_parcelas_total']
        margem_livre.vr_parcelas = data['vr_parcela']
        margem_livre.vr_seguro = data['vr_seguro']
        margem_livre.fl_seguro = data['fl_seguro']
        margem_livre.dt_desembolso = data['dt_desembolso']
        margem_livre.save()
        StatusContrato.objects.create(
            contrato=contract,
            nome=ContractStatus.AGUARDA_ENVIO_LINK.value,
            created_by=user,
        )

    def _atualizar_dados_contrato(self, contrato: Contrato, data, tipo_produto):
        if int(tipo_produto) in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            campos = [
                'contrato_digitacao_manual',
                'cet_ano',
                'cet_mes',
                'limite_pre_aprovado',
                'taxa_efetiva_ano',
                'taxa',
                'vr_iof',
                'vr_iof_adicional',
                'vr_iof_total',
                'vencimento_fatura',
                'seguro',
            ]

            # Aqui, estamos atualizando os planos associados ao contrato
            # seguros aqui !!
            planos = data.get('plano', [])
            for plano in planos:
                plano_obj = Planos.objects.get(id=plano.get('id'))
                contrato.plano.add(plano_obj)
                PlanosContrato.objects.create(
                    contrato=contrato,
                    plano=plano_obj,
                    valor_plano=plano.get('valor'),
                )

        elif int(tipo_produto) in [
            EnumTipoProduto.MARGEM_LIVRE,
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_CORBAN,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
        ]:
            campos = [
                'taxa_efetiva_mes',
                'taxa_efetiva_ano',
                'cet_mes',
                'cet_ano',
                'vr_liberado_cliente',
                'vr_iof',
                'vr_iof_adicional',
            ]
        for campo in campos:
            setattr(contrato, campo, data[campo])
        contrato.save()

    def _set_status_contrato(self, contrato, tipo_produto, user):
        status_map = {
            EnumTipoProduto.CARTAO_BENEFICIO: ContractStatus.FORMALIZACAO_CLIENTE,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE: ContractStatus.FORMALIZACAO_CLIENTE,
            EnumTipoProduto.CARTAO_CONSIGNADO: ContractStatus.FORMALIZACAO_CLIENTE,
            EnumTipoProduto.INSS: ContractStatus.AGUARDA_ENVIO_LINK,
            EnumTipoProduto.INSS_CORBAN: ContractStatus.AGUARDA_ENVIO_LINK,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL: ContractStatus.AGUARDA_ENVIO_LINK,
        }
        if int(tipo_produto) in status_map:
            StatusContrato.objects.create(
                contrato=contrato,
                nome=status_map[int(tipo_produto)].value,
                created_by=user,
            )
        contrato.status = EnumContratoStatus.DIGITACAO
        contrato.save()

    def _criar_contrato(
        self,
        user,
        data,
        tipo_produto,
        cliente,
        quantidade_contratos_por_cliente,
        tokens_contratos,
    ):
        if tipo_produto in [
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ]:
            for contract in Contrato.objects.filter(cliente=cliente):
                if contract.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    try:
                        contract_card_obj = contract.contrato_cartao_beneficio.get()
                        client_card_obj = contract.cliente_cartao_contrato.get()

                        if (
                            client_card_obj.numero_matricula
                            == data.get('numero_matricula')
                            and client_card_obj.tipo_produto == tipo_produto
                            and client_card_obj.tipo_margem == data.get('tipo_margem')
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
                                return Response(
                                    {
                                        'Erro': 'Cliente possui um contrato em andamento para '
                                        'esse produto com a mesma matricula/benefício'
                                    },
                                    status=HTTP_400_BAD_REQUEST,
                                )
                    except ClienteCartaoBeneficio.DoesNotExist:
                        # Lógica para lidar com a situação onde client_card_obj não existe
                        continue

        cliente_dentro_limite_contratos = False

        if data.get('token_contrato'):
            cliente_dentro_limite_contratos = (
                data.get('token_contrato') in tokens_contratos
            )

        if not cliente_dentro_limite_contratos:
            cliente_dentro_limite_contratos = (
                len(tokens_contratos) < quantidade_contratos_por_cliente
            )

        if cliente_dentro_limite_contratos:
            self._atualizar_cliente(cliente, data)
            contrato = self._cria_contrato_produto(
                int(data['tipo_produto']), cliente, user, data
            )
            self._set_status_contrato(contrato, int(data['tipo_produto']), user)
            serializer = CriarContratoSerializer(contrato)
            return Response(serializer.data, status=HTTP_200_OK)

        else:
            return Response(
                {
                    'Erro': 'O CPF cadastrado alcançou o número máximo de contratos ativos.'
                },
                status=HTTP_400_BAD_REQUEST,
            )

    def _create_port_refin(self, request):
        """
        Create a new portability + refinancing contract.

        Args:
            request: An HTTP request containing the contract data.

        Returns:
            Response: A response object with the appropriate status and message.
        """
        try:
            data = request.data

            # Common data shared among all contracts
            # These details are consistent for all contracts in the batch

            if not data:
                return Response(
                    data={'Erro': 'Nenhum dado foi enviado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # TODO: Verificar se vamos usar o product_type
            product_type = data.get('tipo_produto')
            client_id = data.get('id_cliente')
            envelope_token = data.get('token_envelope')
            user = data.get('identificador_usuario')
            proposals = data.get('portabilidade_refinanciamento', [])
            numero_beneficio = data.get('numero_beneficio')

            client = Cliente.objects.filter(id=client_id).first()
            corban_user = UserProfile.objects.filter(unique_id=user).first()
            backoffice_params = ParametrosBackoffice.objects.filter(
                tipoProduto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
            ).first()

            if not backoffice_params:
                return Response(
                    data={
                        'Erro': 'Parâmetros de back office para o produto não encontrados.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if request.user.is_authenticated:
                corban_user = UserProfile.objects.get(
                    identifier=request.user.identifier
                )

            contract_ids = []
            portability_ids = []
            refinancing_ids = []
            is_main_proposal = True

            if any(proposal['troco'] < 0 for proposal in proposals):
                return Response(
                    data={
                        'Erro': 'Não é possível realizar um refinanciamento com troco negativo.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for proposal in proposals:
                # TODO: Refactor to return a list of contract_ids, portability_ids
                # TODO: and refinancing_ids by proposals
                (contract, portability, refinancing) = self._create_contract_port_refin(
                    client=client,
                    product_type=product_type,
                    envelope_token=envelope_token,
                    corban_user=corban_user,
                    proposal=proposal,
                    is_main_proposal=is_main_proposal,
                    numero_beneficio=numero_beneficio,
                )
                is_main_proposal = False
                contract_ids.append(contract.id)
                portability_ids.append(portability.id)
                refinancing_ids.append(refinancing.id)
            if client.escolaridade == EnumEscolaridade.ANALFABETO:
                Contrato.objects.filter(id__in=contract_ids).update(
                    rogado_id=data.get('id_rogado')
                )
                create_client_contract_witnesses(
                    client=client,
                    witnesses_payload=data.get('testemunhas', []),
                    contract_ids=contract_ids,
                )
            return Response(
                data={
                    'contract_ids': contract_ids,
                    'portability_ids': portability_ids,
                    'refinancing_ids': refinancing_ids,
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception('An error occurred when trying to create the contract.')
            return Response(
                data={'Erro': 'Confira os parametros do sistema e tente novamente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _create_port(self, request):
        """
        Create a new portability contract.

        Args:
            request: An HTTP request containing the contract data.

        Returns:
            Response: A response object with the appropriate status and message.
        """
        try:
            data = request.data

            # Common data shared among all contracts
            # These details are consistent for all contracts in the batch

            if not data:
                return Response(
                    data={'Erro': 'Nenhum dado foi enviado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # TODO: Verificar se vamos usar o product_type
            product_type = data.get('tipo_produto')
            client_id = data.get('id_cliente')
            envelope_token = data.get('token_envelope')
            user = data.get('identificador_usuario')
            proposals = data.get('portabilidade', [])
            numero_beneficio = data.get('numero_beneficio')

            client = Cliente.objects.filter(id=client_id).first()
            corban_user = UserProfile.objects.filter(unique_id=user).first()
            backoffice_params = ParametrosBackoffice.objects.filter(
                tipoProduto=EnumTipoProduto.PORTABILIDADE
            ).first()

            if not backoffice_params:
                return Response(
                    data={
                        'Erro': 'Parâmetros de back office para o produto não encontrados.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            in100_data: DadosIn100 = DadosIn100.objects.filter(
                numero_beneficio=numero_beneficio
            ).first()

            self.__validate_negative_margin(
                in100_data=in100_data, contracts_number=len(proposals)
            )

            if request.user.is_authenticated:
                corban_user = UserProfile.objects.get(
                    identifier=request.user.identifier
                )

            contract_ids = []
            portability_ids = []
            is_main_proposal = True
            for proposal in proposals:
                # TODO: Refactor to return a list of contract_ids, portability_ids
                # TODO: and refinancing_ids by proposals
                (contract, portability) = self._create_contract_port(
                    client=client,
                    product_type=product_type,
                    envelope_token=envelope_token,
                    corban_user=corban_user,
                    proposal=proposal,
                    is_main_proposal=is_main_proposal,
                    numero_beneficio=numero_beneficio,
                )
                is_main_proposal = False
                contract_ids.append(contract.id)
                portability_ids.append(portability.id)
            if client.escolaridade == EnumEscolaridade.ANALFABETO:
                Contrato.objects.filter(id__in=contract_ids).update(
                    rogado_id=data.get('id_rogado')
                )
                create_client_contract_witnesses(
                    client=client,
                    witnesses_payload=data.get('testemunhas', []),
                    contract_ids=contract_ids,
                )
            return Response(
                data={
                    'contract_ids': contract_ids,
                    'portability_ids': portability_ids,
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception('An error occurred when trying to create the contract.')
            return Response(
                data={'Erro': 'Confira os parametros do sistema e tente novamente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _create_contract_port_refin(
        self,
        client: Cliente,
        numero_beneficio: str,
        product_type: EnumTipoProduto,
        envelope_token: str,
        corban_user: UserProfile,
        proposal: dict[str, any],
        is_main_proposal: bool = True,
    ) -> Union[tuple[Contrato, Portabilidade, Refinanciamento], Response]:
        """
        Create a contract with portability and refinancing based on a proposal.

        Attempts to create a new contract, portability, and refinancing entries.
        Handles and logs exceptions occurring during the process.

        Parameters:
        client (Cliente): Client associated with the new contract.
        product_type (EnumTipoProduto): Product type for the contract.
        envelope_token (str): Token for the contract envelope.
        corban_user (UserProfile): User profile of the contract creator.
        proposal (dict[str, any]): Proposal details.

        Returns:
        Union[tuple[Contrato, Portabilidade, Refinanciamento], Response]:
        Tuple of created contract entities on success, or error Response on failure.
        """
        cet_year = proposal.get('cet_ano')
        bank = proposal.get('banco')
        outstanding_balance = proposal.get('saldo_devedor')
        term = proposal.get('prazo')
        interest_rate = proposal.get('nova_taxa')
        contract_number = proposal.get('contrato')
        new_installment = proposal.get('nova_parcela')
        entered_installment = proposal.get('parcela')
        new_interest_rate = proposal.get('nova_taxa')
        new_term = proposal.get('novo_prazo')
        free_margin = proposal.get('margem_liberada')
        refin_change = proposal.get('troco')
        refin_total_amount = proposal.get('valor_operacao')

        try:
            contract = Contrato.objects.create(
                cliente=client,
                tipo_produto=product_type,
                cd_contrato_tipo=EnumTipoContrato.REFIN_PORTABILIDADE,
                token_envelope=envelope_token,
                created_by=corban_user,
                corban=corban_user.corban,
                corban_photo=corban_user.corban.corban_name,
                created_by_photo=corban_user.name,
                cet_ano=cet_year,
                is_main_proposal=is_main_proposal,
                numero_beneficio=numero_beneficio,
            )

            portability = Portabilidade.objects.create(
                contrato=contract,
                banco=bank,
                saldo_devedor=outstanding_balance,
                prazo=term,
                taxa=interest_rate,
                numero_contrato=contract_number,
                nova_parcela=new_installment,
                parcela_digitada=entered_installment,
            )

            portability.status = ContractStatus.AGUARDA_ENVIO_LINK.value
            portability.save(update_fields=['status'])

            refinancing = Refinanciamento.objects.create(
                contrato=contract,
                banco=bank,
                saldo_devedor=refin_total_amount,
                prazo=new_term,
                taxa=new_interest_rate,
                numero_contrato=contract_number,
                nova_parcela=new_installment,
                parcela_digitada=entered_installment,
                margem_liberada=free_margin,
                troco=refin_change,
                valor_total=refin_total_amount,
            )

            refinancing.status = ContractStatus.AGUARDA_ENVIO_LINK.value
            refinancing.save(update_fields=['status'])

            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.AGUARDA_ENVIO_LINK.value,
                created_by=corban_user,
            )

            return contract, portability, refinancing

        except Exception:
            logger.exception('Something wrong when trying to create contract')
            return Response(
                {
                    'msg': 'Erro ao criar contrato, verifique os dados e tente novamente.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _create_contract_port(
        self,
        client: Cliente,
        numero_beneficio: str,
        product_type: EnumTipoProduto,
        envelope_token: str,
        corban_user: UserProfile,
        proposal: dict[str, any],
        is_main_proposal: bool = True,
    ) -> Union[tuple[Contrato, Portabilidade], Response]:
        """
        Create a contract with portability based on a proposal.

        Attempts to create a new contract, portability entries.
        Handles and logs exceptions occurring during the process.

        Parameters:
        client (Cliente): Client associated with the new contract.
        product_type (EnumTipoProduto): Product type for the contract.
        envelope_token (str): Token for the contract envelope.
        corban_user (UserProfile): User profile of the contract creator.
        proposal (dict[str, any]): Proposal details.

        Returns:
        Union[tuple[Contrato, Portabilidade], Response]:
        Tuple of created contract entities on success, or error Response on failure.
        """
        cet_year = proposal.get('cet_ano')
        bank = proposal.get('banco')
        outstanding_balance = proposal.get('saldo_devedor')
        term = proposal.get('prazo')
        interest_rate = proposal.get('taxa')
        contract_number = proposal.get('numero_contrato')
        new_installment = proposal.get('nova_parcela')
        entered_installment = proposal.get('parcela_digitada')

        try:
            contract = Contrato.objects.create(
                cliente=client,
                tipo_produto=product_type,
                cd_contrato_tipo=EnumTipoContrato.PORTABILIDADE,
                token_envelope=envelope_token,
                created_by=corban_user,
                corban=corban_user.corban,
                corban_photo=corban_user.corban.corban_name,
                created_by_photo=corban_user.name,
                cet_ano=cet_year,
                is_main_proposal=is_main_proposal,
                numero_beneficio=numero_beneficio,
            )

            portability = Portabilidade.objects.create(
                contrato=contract,
                banco=bank,
                saldo_devedor=outstanding_balance,
                prazo=term,
                taxa=interest_rate,
                numero_contrato=contract_number,
                nova_parcela=new_installment,
                parcela_digitada=entered_installment,
            )

            portability.status = ContractStatus.AGUARDA_ENVIO_LINK.value
            portability.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.AGUARDA_ENVIO_LINK.value,
                created_by=corban_user,
            )

            return contract, portability

        except Exception:
            logger.exception('Something wrong when trying to create contract')
            return Response(
                {
                    'msg': 'Erro ao criar contrato, verifique os dados e tente novamente.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def __validate_negative_margin(self, in100_data: DadosIn100, contracts_number: int):
        """
        Validates if has negative margin and multiple contracts
        Args:
            in100_data: In100 data from client
            contracts_number: Number of contracts to be created

        Raises:
            ValidationError: When contracts number is greater than 1

        """
        if in100_data and in100_data.valor_margem < 0 and contracts_number > 1:
            raise ValidationError({
                'Erro': 'Você só pode realizar um contrato com a margem negativa'
            })


# TODO : Retirar essa api quando a de port criar contratos for testada pois ficara obsoleta
class CriarContratoPortabilidade(GenericAPIView):
    """
    API used for creating a portability contract during the origination process.
    """

    serializer_class = CriarContratoPortabilidadeSerializer

    @transaction.atomic()
    def post(self, request: Request) -> Response:
        """
        Create a new portability contract.

        Args:
            request: An HTTP request containing the contract data.

        Returns:
            Response: A response object with the appropriate status and message.
        """
        try:
            proposals: list[dict[str, any]] = request.data

            product_type_number: int = proposals[0]['tipo_produto']
            client_id: int = proposals[0]['id_cliente']
            envelope_token: str = proposals[0]['token_envelope']
            user_id: int = proposals[0]['identificador_usuario']

            client: Cliente = Cliente.objects.filter(id=client_id).first()
            in100_data: DadosIn100 = DadosIn100.objects.filter(cliente=client).first()

            self.__validate_negative_margin(
                in100_data=in100_data, contracts_number=len(proposals)
            )

            # Check the client number of contracts to create protability
            MaxContractByCPFValidator(
                client_id=client_id,
                product_type=ProductTypeEnum(product_type_number),
                proposals_amount=len(proposals) or 1,
            ).check_active_contracts()

            corban_user: UserProfile = UserProfile.objects.get(unique_id=user_id)
            if request.user.is_authenticated:
                corban_user: UserProfile = UserProfile.objects.get(
                    identifier=request.user.identifier
                )
            # Create contracts and portability contracts
            contract_ids = []
            portability_ids = []
            # First contract is always the main proposal
            is_main_proposal = True
            for proposal in proposals:
                contract, portability = self.__create_contract_and_portability(
                    client=client,
                    product_type=product_type_number,
                    envelope_token=envelope_token,
                    corban_user=corban_user,
                    cet_year=proposal['cet_ano'],
                    bank=proposal['banco'],
                    outstanding_balance=proposal['saldo_devedor'],
                    term=proposal['prazo'],
                    interest_rate=proposal['taxa'],
                    contract_number=proposal['numero_contrato'],
                    new_installment=proposal['nova_parcela'],
                    entered_installment=proposal['parcela_digitada'],
                    main_proposal=is_main_proposal,
                )
                is_main_proposal = False
                contract_ids.append(contract.id)
                portability_ids.append(portability.id)
            return Response(
                data={'contract_ids': contract_ids, 'portability_ids': portability_ids},
                status=HTTP_200_OK,
            )
        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                'Something wrong when creating contracts and portability contracts'
            )
            raise ValidationError(
                detail={'Erro': 'Confira os parametros do sistema e tente novamente.'},
                code=HTTP_400_BAD_REQUEST,
            ) from e

    @staticmethod
    def __create_contract_and_portability(
        client: Cliente,  # cliente
        product_type: int,  # tipo_produto
        envelope_token: str,  # token_envelope
        corban_user: UserProfile,  # usuario_corban
        cet_year: Decimal,  # cet_ano
        bank: str,  # banco
        outstanding_balance: float,  # saldo_devedor
        term: int,  # prazo
        interest_rate: Decimal,  # taxa
        contract_number: str,  # numero_contrato
        new_installment: Decimal,  # nova_parcela
        entered_installment: Decimal,  # parcela_digitada
        main_proposal: bool = True,  # Is main envelope proposal
    ) -> tuple[Contrato, Portabilidade]:
        """
        Create contracts for portability purposes.

        Args:
            client (Cliente): The client associated with the contract.
            product_type (int): The type of product for the contract.
            envelope_token (str): The token associated with the envelope.
            corban_user (UserProfile): The Corban user responsible for creating the contract.
            cet_year (Decimal): The CET (Cost of Total Effective) year for the contract.
            bank (str): The bank involved in the contract.
            outstanding_balance (float): The outstanding balance for the contract.
            term (int): The term or duration of the contract in months or years.
            interest_rate (Decimal): The interest rate applied to the contract.
            contract_number (str): The unique contract number.
            new_installment (Decimal): The new installment amount for the contract.
            entered_installment (Decimal): The installment amount entered during contract creation.

        Returns:
            tuple[Contrato, Portabilidade]: A tuple containing the Contrato and Portabilidade instances created.

        Raises:
            ValidationError: If there is an error in creating the contract, typically due to invalid data inputs.
        """
        try:
            contract: Contrato = Contrato.objects.create(
                cliente=client,
                tipo_produto=product_type,
                cd_contrato_tipo=4,
                token_envelope=envelope_token,
                created_by=corban_user,
                corban=corban_user.corban,
                corban_photo=corban_user.corban.corban_name,
                created_by_photo=corban_user.name,
                cet_ano=cet_year,
                is_main_proposal=main_proposal,
            )
            portability: Portabilidade = Portabilidade.objects.create(
                contrato=contract,
                banco=bank,
                saldo_devedor=outstanding_balance,
                prazo=term,
                taxa=interest_rate,
                numero_contrato=contract_number,
                nova_parcela=new_installment,
                parcela_digitada=entered_installment,
            )
            portability.status = ContractStatus.AGUARDA_ENVIO_LINK.value
            portability.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.AGUARDA_ENVIO_LINK.value,
                created_by=corban_user,
            )
            return contract, portability
        except Exception as e:
            raise ValidationError(
                detail={
                    'Erro': 'Erro ao criar contrato, verifique os dados e tente novamente.'
                },
                code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    @staticmethod
    def __validate_negative_margin(in100_data: DadosIn100, contracts_number: int):
        """
        Validates if has negative margin and multiple contracts
        Args:
            in100_data: In100 data from client
            contracts_number: Number of contracts to be created

        Raises:
            ValidationError: When contracts number is greater than 1

        """
        if in100_data and in100_data.valor_margem < 0 and contracts_number > 1:
            raise ValidationError({
                'Erro': 'Você só pode realizar um contrato com a margem negativa'
            })


class AssinarTermoIN100(GenericAPIView):
    """API utilizada para realizar a assinatura do termo de autorização e
    enviar o termo para a QiTech realizar a consulta dos dados do Cliente"""

    permission_classes = [AllowAny]

    def validar_ip(self, ip) -> bool:
        regex = (
            r'^\s*((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)'
            r'{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\s*$)|(\s*'
            r'((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}'
            r':){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
            r'(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}'
            r':){5}(((::[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?'
            r'\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}'
            r':){4}(((::[0-9A-Fa-f]{1,4}){1,3})|((::[0-9A-Fa-f]{1,4})?:((25[0-5]|'
            r'2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))'
            r'|:))|(([0-9A-Fa-f]{1,4}:){3}(((::[0-9A-Fa-f]{1,4}){1,4})|((::'
            r'[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
            r'(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}'
            r':){2}(((::[0-9A-Fa-f]{1,4}){1,5})|((::[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|'
            r'2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))'
            r'|:))|(([0-9A-Fa-f]{1,4}:){1}(((::[0-9A-Fa-f]{1,4}){1,6})|((::'
            r'[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
            r'(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:((::[0-9A-Fa-f]'
            r'{1,4}){1,7})|((::[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?'
            r'\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$'
        )
        return bool(re.match(regex, ip))

    def post(self, request):
        try:
            id_cliente = request.data['id_cliente']
            latitude = request.data['latitude']
            longitude = request.data['longitude']
            ip_publico = request.data['ip_publico']
            numero_beneficio = request.data.get('numero_beneficio')
            cliente = Cliente.objects.filter(id=id_cliente).first()
            cliente.IP_Cliente = ip_publico
            cliente.save()
            if not self.validar_ip(ip_publico):
                return Response(
                    {
                        'Erro': 'Ocorreu um erro ao salvar o IP do cliente. '
                        'Verifique se a geolocalização está ativada e tente novamente.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            in100, _ = DadosIn100.objects.update_or_create(
                cliente=cliente, numero_beneficio=numero_beneficio
            )
            in100.in100_data_autorizacao = datetime.now(timezone.utc)
            in100.save()

            assinatura_termo_in100(latitude, longitude, ip_publico, cliente, in100)
            consulta_beneficio_in100_portabilidade(cliente, numero_beneficio, in100)
            return Response({'Documentos assinados com sucesso!'}, status=HTTP_200_OK)

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Houve um erro ao Assinar os Termos.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DadosIn100APIView(GenericAPIView):
    """API utilizada para salvar os dados informados pelo cliente na Identificação"""

    def get_permissions(self):
        # Caso seja apenas o GET, exige autenticação, em outros casos passa como era anteriormente
        if self.request and self.request.method == 'GET':
            return (IsAuthenticated(),)
        return super().get_permissions()

    def get(self, request):
        # TODO Refactor para obter como parâmetro de rota e não query params!
        # client_id = request.query_params.get('id_cliente')
        numero_beneficio = request.query_params.get('numero_beneficio')
        try:
            return Response(
                data=DadosIN100Serializer(
                    instance=DadosIn100.objects.get(numero_beneficio=numero_beneficio)
                ).data,
            )

        except DadosIn100.DoesNotExist as e:
            raise ValidationError({'erro': 'In100 do cliente não encontrada'}) from e

    def post(self, request):
        try:
            id = request.data['id_cliente']
            numero_beneficio = request.data['numero_beneficio']
            cliente = Cliente.objects.get(id=id)

            in100, _ = DadosIn100.objects.update_or_create(
                cliente=cliente, numero_beneficio=numero_beneficio
            )
            if in100 and not in100.retornou_IN100:
                # Verificar se os campos opcionais estão presentes no request.data
                if 'numero_beneficio' in request.data:
                    in100.numero_beneficio = request.data['numero_beneficio']
                if 'cd_beneficio_tipo' in request.data:
                    in100.cd_beneficio_tipo = request.data['cd_beneficio_tipo']
                if 'valor_beneficio' in request.data:
                    in100.valor_beneficio = request.data['valor_beneficio']
                if 'valor_liquido' in request.data:
                    in100.valor_liquido = request.data['valor_liquido']
                if 'valor_margem' in request.data:
                    in100.valor_margem = request.data['valor_margem']
                in100.save()

                salvando_retorno_IN100_contrato(in100, in100.numero_beneficio)
            return Response({'msg': 'Os dados foram salvos com sucesso!'})
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Houve um erro ao tentar salvar os dados.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EnvioSmsIN100(GenericAPIView):
    """
    API para envio do SMS do link da IN100 por sms para o cliente
    """

    def post(self, request):
        produto = request.data['produto']
        numero_telefone = request.data['numero_telefone']
        try:
            try:
                id_cliente = request.data['id_cliente']
                cliente = Cliente.objects.filter(id=id_cliente).first()
            except Exception as e:
                print(e)
                cpf_cliente = request.data['cpf_cliente']
                cliente = Cliente.objects.filter(nu_cpf=cpf_cliente).first()

            parametros_backoffice = ParametrosBackoffice.objects.get(
                tipoProduto=produto, ativo=True
            )

            url = parametros_backoffice.url_formalizacao

            url_formalizacao_longa = None
            if produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                url_formalizacao_longa = f'{url}/autorizacao-in100/{cliente.nu_cpf_}'
            elif produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                url_formalizacao_longa = f'{url}/in100/{cliente.nu_cpf_}'

            url_formalizacao_curta = generate_short_url(long_url=url_formalizacao_longa)

            if produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                mensagem = f'Ola {cliente.nome_cliente}, acesse o link para autorizar a consulta dos dados do seu INSS'
            elif produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                mensagem = f'{parametros_backoffice.texto_sms_formalizacao} {url_formalizacao_curta}'

            zenvia_sms(cliente.nu_cpf_, numero_telefone, mensagem)
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


class ValidarContrato(APIView):
    """
    Atualização de contratos e os seus status durante a formalização
    """

    permission_classes = [HasAPIKey | AllowAny]

    def patch(self, request, *args, **kwargs):
        payload = request.data
        token_envelope = request.data['token']
        numero_cpf = request.data['cpf']

        # validate UNICO score
        # from contract.api.views.unico_score_contract_validator import (
        #     UnicoScoreContractValidator
        # )
        # envelope = EnvelopeContratos.objects.get(
        #     token_envelope=token_envelope)
        # for contract in envelope.contracts:
        #     UnicoScoreContractValidator(contract).validate()

        validar_contrato_assync.apply_async(
            args=[payload, token_envelope, numero_cpf, '00000000099']
        )
        return Response(
            {
                'msg': 'Contratos enviados para validação.',
            },
            status=HTTP_200_OK,
        )


class PesquisaContratos(GenericAPIView):
    """
    Tela de listagem de contratos para pesquisa de contratos
    """

    def post(self, request):
        try:
            context = {}
            contratos = Contrato.objects.all()

            cpf = request.data['cpf']
            numero_contrato = request.data['contrato']
            numero_matricula = request.data['matricula']
            nome_cliente = request.data['cliente']
            status = request.data['status']

            if cpf:
                contratos = Contrato.objects.filter(cliente__nuCpf=cpf)
            if numero_contrato:
                contratos = Contrato.objects.filter(nuContratoFacta=numero_contrato)
            if numero_matricula:
                contratos = Contrato.objects.filter(
                    cliente__tipoCliente=numero_matricula
                )
            if nome_cliente:
                contratos = Contrato.objects.filter(cliente__nmCliente=nome_cliente)
            if status:
                contratos = Contrato.objects.filter(status=status)

            if cpf or numero_contrato or numero_matricula or nome_cliente or status:
                serializer = ContratoSerializer(
                    contratos, many=True, context={'request': request}
                )
                context['contratos'] = contratos
            else:
                serializer = ContratoSerializer(
                    contratos, many=True, context={'request': request}
                )
            return Response(serializer.data)
        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'Erro': 'Não foi possível encontrar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


@permission_classes((AllowAny,))
class ContratoKPI(RetrieveAPIView):
    """API that returns contract count for backoffice boxes"""

    serializer_class = ContratoKPISerializer

    def get(self, request, *args, **kwargs):
        from django.utils import timezone

        try:
            type_product_contract = int(request.GET.get('tipo_produto', 0))
            status = int(request.GET.get('status', 0))
            qs = Contrato.objects.all()
            if type_product_contract:
                qs = qs.filter(tipo_produto=type_product_contract)
            if status:
                if status == 41:
                    qs = qs.filter(
                        Q(contrato_portabilidade__status__in=STATUS_REPROVADOS)
                        | Q(contrato_margem_livre__status__in=STATUS_REPROVADOS)
                        | Q(contrato_refinanciamento__status__in=STATUS_REPROVADOS)
                    )
                elif status == 33:
                    ids_contratos_status = (
                        StatusContrato.objects.filter(
                            nome=ContractStatus.SALDO_RETORNADO.value,
                            data_fase_inicial__date=timezone.localdate(),
                        )
                        .values_list('contrato_id', flat=True)
                        .distinct()
                    )
                    qs = qs.filter(
                        Q(
                            contrato_portabilidade__status__in=(
                                STATUS_APROVADOS + STATUS_PENDENTE + STATUS_REPROVADOS
                            )
                        )
                        & Q(
                            id__in=ids_contratos_status
                        )  # Usa os IDs dos contratos obtidos anteriormente
                    )
                elif status == 1000:
                    ids_contratos_status = (
                        StatusContrato.objects.filter(
                            nome=ContractStatus.SALDO_RETORNADO.value,
                            data_fase_inicial__date=timezone.localdate(),
                        )
                        .values_list('contrato_id', flat=True)
                        .distinct()
                    )
                    qs = qs.filter(
                        Q(contrato_portabilidade__status__in=STATUS_APROVADOS)
                        & Q(
                            id__in=ids_contratos_status
                        )  # Usa os IDs dos contratos obtidos anteriormente
                    )
                elif status == 1001:
                    ids_contratos_status = (
                        StatusContrato.objects.filter(
                            nome=ContractStatus.SALDO_RETORNADO.value,
                            data_fase_inicial__date=timezone.localdate(),
                        )
                        .values_list('contrato_id', flat=True)
                        .distinct()
                    )
                    qs = qs.filter(
                        Q(contrato_portabilidade__status__in=STATUS_PENDENTE)
                        & Q(
                            id__in=ids_contratos_status
                        )  # Usa os IDs dos contratos obtidos anteriormente
                    )
                elif status == 1002:
                    ids_contratos_status = (
                        StatusContrato.objects.filter(
                            nome=ContractStatus.SALDO_RETORNADO.value,
                            data_fase_inicial__date=timezone.localdate(),
                        )
                        .values_list('contrato_id', flat=True)
                        .distinct()
                    )
                    qs = qs.filter(
                        Q(contrato_portabilidade__status__in=STATUS_REPROVADOS)
                        & Q(
                            id__in=ids_contratos_status
                        )  # Usa os IDs dos contratos obtidos anteriormente
                    )
                else:
                    qs = qs.filter(
                        Q(contrato_portabilidade__status=status)
                        | Q(contrato_margem_livre__status=status)
                        | Q(contrato_refinanciamento__status=status)
                    )
            sum_contract = self.sum_contracts(qs)
            return Response(
                {'count': qs.count(), 'sum_contract': round(sum_contract, 2)},
                status=HTTP_200_OK,
            )

        except Exception:
            newrelic.agent.notice_error()
            return Response(
                {'msg': 'An error occurred in the backoffice boxes, contact support'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def sum_contracts(self, contracts):
        sum_contract = (
            contracts.aggregate(
                total=Sum(
                    Case(
                        When(
                            tipo_produto=EnumTipoProduto.PORTABILIDADE,
                            then=Coalesce(
                                F('contrato_portabilidade__saldo_devedor_atualizado'),
                                F('contrato_portabilidade__saldo_devedor'),
                                Value(0),
                            ),
                        ),
                        When(
                            tipo_produto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                            then=Coalesce(
                                F('contrato_refinanciamento__valor_total'), Value(0)
                            ),
                        ),
                        When(
                            tipo_produto=EnumTipoProduto.MARGEM_LIVRE,
                            then=Coalesce(
                                F('contrato_margem_livre__vr_contrato'), Value(0)
                            ),
                        ),
                        default=Value(0),
                        output_field=FloatField(),
                    )
                )
            )['total']
            or 0
        )

        return float(sum_contract)


class SimulacaoPortabilidade(GenericAPIView):
    """
    Envio de dados para realizar simulação da Portabilidade.
    """

    serializer_class = SimulacaoPortabilidadeSerializer

    @staticmethod
    def validate_simulation_rules(
        total_amount: float,
        typed_installment: float,
        margin_value: float,
        final_balance_due: float,
        installments_number=None,
        client_id=None,
        numero_beneficio=None,
    ) -> tuple[bool, str]:
        """
        Validates if simulation rules is valid.

        Args:
            total_amount: Total amount from simulation
            typed_installment: Installment typed on simulation form
            margin_value: Client margin value received
            final_balance_due: the amount of money owed or outstanding balance as of the most recent or last recorded
            installments_number: Installments total number
            client_id: cpf client string

        Returns:
            Tuple with is_valid and error message if exists

        """
        if typed_installment and isinstance(margin_value, (int, float)):
            if total_amount < 35:
                return False, 'Nova parcela muito pequena'
            elif total_amount > typed_installment:
                return False, 'Nova parcela maior que parcela atual'
            elif total_amount == typed_installment:
                return False, 'Nova parcela igual a parcela atual'
            elif margin_value < 0 and total_amount > typed_installment + margin_value:
                return (
                    False,
                    'Nova parcela é maior que a parcela atual mais a margem disponível',
                )

        # validate PORTABILIDADE contract minimum value
        product_paramters = ParametrosProduto.objects.filter(
            tipoProduto=EnumTipoProduto.PORTABILIDADE
        ).first()
        min_value = product_paramters.valor_minimo_emprestimo
        if final_balance_due < min_value:
            msg = 'Valor minimo para esse tipo de contrato é %0.2f' % min_value
            return (False, msg)

        if client_id and installments_number:
            return validate_client_installments_number(
                numero_beneficio=numero_beneficio,
                installments_number=installments_number,
            )

        return True, ''

    def post(self, request):
        payload = request.data

        taxa_de_juros_mensal = payload.get('taxa_de_juros_mensal')
        numero_de_parcelas = payload.get('numero_de_parcelas')
        ultimo_devido_saldo = payload.get('ultimo_devido_saldo')

        parcela_digitada = payload.get('parcela_digitada')
        valor_margem = payload.get('valor_margem')

        client_id = payload.get('id_cliente')
        numero_beneficio = payload.get('numero_beneficio')

        error_msg = 'Não foi possivel simular portabilidade'
        try:
            simulacao = simulacao_portabilidade_financeira_hub(
                taxa_de_juros_mensal, numero_de_parcelas, ultimo_devido_saldo
            )
            if simulacao['retornado']:
                is_valid, error_message = self.validate_simulation_rules(
                    simulacao['total_amount'],
                    parcela_digitada,
                    valor_margem,
                    ultimo_devido_saldo,
                    numero_de_parcelas,
                    client_id,
                    numero_beneficio,
                )
                simulacao['is_valid'] = is_valid
                simulacao['error_message'] = error_message
                return Response(simulacao, status=HTTP_200_OK)
            else:
                return Response(
                    {'Erro': f'{error_msg}, Contacte um Administrador'},
                    status=HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logging.exception(
                f'Beneficio: ({str(numero_beneficio)}) - {error_message} {e}',
                exc_info=True,
            )

            return Response(
                {'Erro': error_message},
                status=HTTP_400_BAD_REQUEST,
            )


def link_formalizacao_envelope(token_envelope, user):
    """Criar link de formalização para contratos no envelope."""
    from contract.products.portabilidade.tasks import insert_proposal_port_refin_async

    contratos = Contrato.objects.filter(token_envelope=token_envelope)
    short_url = ''
    for contrato in contratos:
        parametros_backoffice = ParametrosBackoffice.objects.get(
            ativo=True, tipoProduto=contrato.tipo_produto
        )
        token = contrato.token_envelope
        try:
            url = parametros_backoffice.url_formalizacao
            url_formalizacao_longa = f'{url}/{token}'
        except Exception as e:
            logger.error(f'Erro ao montar a url de formalizacao longa: {e}')

        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
            ultimo_status = StatusContrato.objects.latest(
                'contrato', 'data_fase_inicial'
            )
            if ultimo_status.nome != ContractStatus.ANDAMENTO_FORMALIZACAO.value:
                user = UserProfile.objects.get(identifier=user.identifier)
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.ANDAMENTO_FORMALIZACAO.value,
                    created_by=user,
                )
                contrato_cartao.status = ContractStatus.ANDAMENTO_FORMALIZACAO.value
                contrato.status = EnumContratoStatus.DIGITACAO
                contrato.save()
                contrato_cartao.save()
            try:
                get_dados_contrato(contrato, contrato_cartao)
            except Exception as e:
                logger.error(f'Erro ao obter dados do contrato: {e}')
        if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
            ultimo_status = StatusContrato.objects.latest(
                'contrato', 'data_fase_inicial'
            )
            if ultimo_status.nome != ContractStatus.ANDAMENTO_FORMALIZACAO.value:
                user = UserProfile.objects.get(identifier=user.identifier)
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.ANDAMENTO_FORMALIZACAO.value,
                    created_by=user,
                )
                contrato_saque.status = ContractStatus.ANDAMENTO_FORMALIZACAO.value
                contrato.status = EnumContratoStatus.DIGITACAO
                contrato.save()
                contrato_saque.save()
            get_dados_contrato_saque_complementar(contrato, contrato_saque)

        if contrato.tipo_produto in (
            EnumTipoProduto.MARGEM_LIVRE,
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
        ):
            in100 = DadosIn100.objects.filter(
                numero_beneficio=contrato.numero_beneficio
            ).first()
            if in100.retornou_IN100:
                parametros_produto = ParametrosProduto.objects.filter(
                    tipoProduto=contrato.tipo_produto
                ).first()

                insere_proposta_margem_livre_financeira_hub(
                    contrato,
                    float(contrato.taxa_efetiva_mes) / 100,
                    'calendar_days',
                    float(parametros_produto.multa_contrato_margem_livre) / 100,
                )
            else:
                atualizar_status_contratos(
                    contrato,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                    '-',
                    user=None,
                )
        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            if (
                contrato.cliente
                and contrato.cliente.escolaridade == EnumEscolaridade.ANALFABETO
            ):
                insert_portability_proposal(str(contrato.token_contrato))
            else:
                insert_portability_proposal.apply_async(
                    args=[str(contrato.token_contrato)]
                )
            contrato.refresh_from_db()
            user = UserProfile.objects.get(identifier=user.identifier)
            status_envio_link_portabilidade(contrato, user)

        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            if settings.ENVIRONMENT != EnvironmentEnum.PROD.value:
                insert_proposal_port_refin_async(contrato.id, user.id)
            else:
                qi_tech = HandleQitechResponse(contrato)
                qi_tech.insert_proposal_port_refin_response()
                user = UserProfile.objects.get(identifier=user.identifier)
                status_envio_link_portabilidade(contrato, user)
                refin = Refinanciamento.objects.filter(contrato=contrato).first()
                port = Portabilidade.objects.filter(contrato=contrato).first()
                refin.status = port.status
                refin.save()

        short_url = contrato.url_formalizacao or generate_short_url(
            long_url=url_formalizacao_longa
        )
        if not short_url:
            # log data
            message = 'A short URL não pode ser gerada para o contrato %d' % contrato.id
            logger.info(message)
            raise ValidationError(
                detail={'error': 'Error on generate short url of proposal'},
                code=status.HTTP_400_BAD_REQUEST,
            )

        contrato.link_formalizacao_criado_em = datetime.now()
        contrato.url_formalizacao = short_url
        cliente = contrato.cliente
        if cliente and cliente.escolaridade == EnumEscolaridade.ANALFABETO:
            contrato.url_formalizacao_rogado = (
                contrato.url_formalizacao_rogado
                or generate_short_url(long_url=f'{url_formalizacao_longa}/rogado')
            )

        contrato.save(
            update_fields=[
                'link_formalizacao_criado_em',
                'url_formalizacao',
                'url_formalizacao_rogado',
            ]
        )

    return short_url


class StatusContratoPortabilidade(GenericAPIView):
    """
    Mudar status contrato na jornada de formalização.
    """

    permission_classes = [AllowAny]
    serializer_class = StatusContratoPortabilidadeSerializer

    def post(self, request):
        payload = request.data
        token_contrato = payload.get('token_contrato')
        status = payload.get('status')

        try:
            Contrato.objects.filter(token_contrato=token_contrato).update(status=status)
            return Response('Status contrato anexado com sucesso.', status=HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(
                'Não foi possível realizar inclusão da proposta na financeira.',
                status=HTTP_400_BAD_REQUEST,
            )
