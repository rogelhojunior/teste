import logging
from datetime import datetime

import newrelic.agent
from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

import handlers.webhook_qitech as qitech_apis
from api_log.constants import EnumStatusCCB
from contract.constants import EnumContratoStatus, EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
)
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.especie import EspecieIN100
from contract.products.portabilidade.api.serializers import (
    DetalheParametrosProdutoSerializer,
)
from contract.products.portabilidade.tasks import (
    approve_portability_contract,
    deny_portability_contract,
)
from contract.products.portabilidade.views import (
    validacao_regra_morte,
    validar_regra_especie,
)
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
    RefuseProposalFinancialFreeMargin,
    AcceptProposalFinancialPortability,
    SubmitFinancialPortabilityProposal,
)
from contract.services.persistance.contract import (
    change_main_contract_and_create_new_status,
    get_secondary_contracts,
)
from core.constants import EnumAcaoCorban
from core.models import Cliente, ParametrosBackoffice
from core.models.cliente import DadosBancarios
from core.models.parametro_produto import ParametrosProduto
from core.serializers import AutorizacaoDadosBancariosSerializer, IN100Serializer
from core.utils import exclude_all_check_rules, generate_short_url, alterar_status
from custom_auth.models import UserProfile
from handlers.consultas import consulta_regras_hub_receita_corban
from handlers.portabilidade_in100 import consulta_beneficio_in100_portabilidade
from handlers.webhook_qitech.enums import PendencyReasonEnum
from handlers.zenvia_sms import zenvia_sms
from utils.bank import get_client_bank_data

logger = logging.getLogger('digitacao')


class AcaoCorban(GenericAPIView):
    @transaction.atomic()
    def post(self, request):
        """
        Process a Corban action (Approve, Pend, or Decline) on a contract.
        """
        try:
            token_contrato = request.data.get('token_contrato')
            acao_corban = request.data.get('acao_corban')
            observacao = request.data.get('observacao', '')

            if not token_contrato or not acao_corban:
                return Response(
                    {'Erro': 'Token de contrato e ação Corban são necessários.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            contrato = Contrato.objects.get(token_contrato=token_contrato)
            ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
            if ultimo_status.nome is not ContractStatus.CHECAGEM_MESA_CORBAN.value:
                return Response(
                    {
                        'Erro': 'Ação não pode ser realizada, o contrato já avançou na esteira.'
                    },
                    status=HTTP_400_BAD_REQUEST,
                )

            user = UserProfile.objects.get(identifier=request.user.identifier)

            if acao_corban == EnumAcaoCorban.APROVAR:
                return self.approve_contract(contrato, user)
            elif acao_corban == EnumAcaoCorban.PENDENCIAR:
                return self.pend_contract(contrato, user, observacao, request)
            elif acao_corban == EnumAcaoCorban.RECUSAR:
                return self.decline_contract(contrato, user, observacao)
            else:
                return Response(
                    {'Erro': 'Ação Corban não reconhecida.'},
                    status=HTTP_400_BAD_REQUEST,
                )
        except Contrato.DoesNotExist:
            return Response(
                {'Erro': 'Contrato não encontrado'}, status=HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu um erro ao processar a ação Corban.'},
                status=HTTP_400_BAD_REQUEST,
            )

    def is_refin_product(self, contract: Contrato):
        return contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO

    def is_card_product(self, contract: Contrato):
        return contract.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        )

    def get_product(self, contract: Contrato):
        if contract.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            return Portabilidade.objects.get(contrato=contract)
        elif contract.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            return MargemLivre.objects.get(contrato=contract)
        elif self.is_card_product(contract):
            return CartaoBeneficio.objects.get(contrato=contract)

        return None

    def should_check_dataprev(self, contract: Contrato, product: CartaoBeneficio):
        return product.convenio.convenio_inss and contract.contrato_digitacao_manual

    @transaction.atomic()
    def approve_contract(self, contract: Contrato, user: UserProfile):
        """
        Approve a contract in the Corban process.
        """
        try:
            product = self.get_product(contract)

            next_status = ContractStatus.CHECAGEM_MESA_FORMALIZACAO

            if self.is_card_product(contract):
                if self.should_check_dataprev(contract, product):
                    next_status = ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV

            statuses = [
                StatusContrato(contrato=contract, nome=status, created_by=user)
                for status in [
                    ContractStatus.APROVADA_MESA_CORBAN.value,
                    next_status.value,
                ]
            ]
            StatusContrato.objects.bulk_create(statuses)

            if self.is_refin_product(contract):
                refin = Refinanciamento.objects.get(contrato=contract)
                refin.status = next_status.value
                refin.save(update_fields=['status'])

            product.status = next_status.value
            product.save(update_fields=['status'])

            contract.status = EnumContratoStatus.MESA
            contract.save(update_fields=['status'])

            return Response({'Aprovado pela mesa Corban'}, status=HTTP_200_OK)
        except Exception as e:
            logging.error(f'Ocorreu um erro ao aprovar o contrato: {e}')
            return Response(
                {'Erro': 'Ocorreu um erro ao aprovar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )

    @transaction.atomic()
    def pend_contract(self, contract: Contrato, user: UserProfile, note: str, request):
        """
        Place a contract in pending status in the Corban process.
        """
        try:
            pendente_documento = request.data.get('pendente_documento', False)
            pendente_selfie = request.data.get('pendente_selfie', False)
            contratos_pendentes = []

            contratos = Contrato.objects.filter(token_envelope=contract.token_envelope)
            for contract in contratos:
                if pendente_documento:
                    contract.pendente_documento = True
                if pendente_selfie:
                    contract.selfie_pendente = True

                contract.status = EnumContratoStatus.MESA
                contract.save()

                produto = self.get_product(contract)

                # Change status when contract is main proposal
                # TODO add filter in loop queryset.
                if contract.is_main_proposal or self.is_card_product(contract):
                    next_status = ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN
                    produto.status = next_status.value
                    produto.save(update_fields=['status'])

                    if self.is_refin_product(contract):
                        refin = Refinanciamento.objects.get(contrato=contract)
                        refin.status = next_status.value
                        refin.save(update_fields=['status'])

                    StatusContrato.objects.create(
                        contrato=contract,
                        nome=next_status.value,
                        created_by=user,
                        descricao_mesa=note,
                    )

                    contratos_pendentes.append(str(contract.pk))

            cliente = contract.cliente
            mensagem = f'{cliente.nome_cliente}, sua proposta foi pendenciada e será necessário regularizá-la através do link: {contract.url_formalizacao}'
            zenvia_sms(cliente.nu_cpf, cliente.telefone_celular, mensagem)

            return Response(
                {
                    'Sucesso': f"Contratos {', '.join(contratos_pendentes)} - {cliente} PENDENCIADOS."
                },
                status=HTTP_200_OK,
            )
        except Exception as e:
            logging.error(f'Ocorreu um erro ao pendenciar o contrato: {e}')
            return Response(
                {'Erro': 'Ocorreu um erro ao pendenciar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )

    @transaction.atomic()
    def decline_contract(self, contract: Contrato, user: UserProfile, note: str):
        """
        Decline a contract in the Corban process.
        """
        try:
            contract.status = EnumContratoStatus.CANCELADO
            contract.save(update_fields=['status'])

            product = self.get_product(contract)
            next_status = ContractStatus.REPROVADA_MESA_CORBAN

            product.status = next_status.value
            product.save()

            if self.is_refin_product(contract):
                refin = Refinanciamento.objects.get(contrato=contract)
                refin.status = next_status.value
                refin.save(update_fields=['status'])

            StatusContrato.objects.create(
                contrato=contract,
                nome=next_status.value,
                created_by=user,
                descricao_mesa=note,
            )

            change_main_contract_and_create_new_status(contract, user)

            return Response(
                {f'Contrato {contract.id} - {contract.cliente} REPROVADO.'},
                status=HTTP_200_OK,
            )
        except Exception as e:
            logging.error(f'Ocorreu um erro ao recusar o contrato: {e}')
            return Response(
                {'Erro': 'Ocorreu um erro ao recusar o contrato.'},
                status=HTTP_400_BAD_REQUEST,
            )


def aprova_contrato_portabilidade_automatico(contrato):
    """Aprovação do contrato automaticamente"""
    token_contrato = contrato.token_contrato
    contrato_portabilidade = Portabilidade.objects.get(contrato=contrato)
    ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()

    try:
        # Verificar se o contrato foi assinado
        if not contrato.contrato_assinado:
            ultimo_status.descricao_mesa = 'Pendente Assinatura'
            ultimo_status.save()
        # Verificar se o token do contrato existe
        if not token_contrato:
            ultimo_status.descricao_mesa = 'Contrato não encontrado'
            ultimo_status.save()
        # Enviar assinatura para a API
        resposta_assinatura = qitech_apis.API_qitech_envio_assinatura(token_contrato)
        if not resposta_assinatura:
            contrato_portabilidade.sucesso_envio_assinatura = False
            contrato_portabilidade.motivo_envio_assinatura = (
                'Erro na API de envio de Assinatura QITECH (400)'
            )
            ultimo_status.descricao_mesa = 'Erro no envio de Assinatura QITECH'
            ultimo_status.save()
        contrato_portabilidade.sucesso_envio_assinatura = True
        contrato_portabilidade.save()
        # Enviar documentos para a API
        resposta_documentos = qitech_apis.API_qitech_documentos(token_contrato)
        if not resposta_documentos:
            ultimo_status.descricao_mesa = 'Erro no envio dos documentos'
            ultimo_status.save()
            contrato_portabilidade.sucesso_documentos_linkados = False
            contrato_portabilidade.motivo_documentos_linkados = (
                'Erro na QITECH ao conectar os documentos na PROPOSTA (400)'
            )
            contrato_portabilidade.save()
        contrato_portabilidade.sucesso_documentos_linkados = True
        contrato_portabilidade.save()

        if SubmitFinancialPortabilityProposal(contract=contrato).execute():
            contrato_portabilidade.status = (
                ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value
            )
            contrato_portabilidade.save()
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
                descricao_mesa='Contrato Submetido Para a QITECH',
            )
            contrato_portabilidade = Portabilidade.objects.get(contrato=contrato)
            contrato_portabilidade.status = ContractStatus.AGUARDA_RETORNO_SALDO.value
            contrato_portabilidade.dt_envio_proposta_CIP = datetime.now()
            contrato_portabilidade.save()
            StatusContrato.objects.create(
                contrato=contrato, nome=ContractStatus.AGUARDA_RETORNO_SALDO.value
            )
            contrato.status = EnumContratoStatus.EM_AVERBACAO
            contrato.save()
        else:
            ultimo_status.descricao_mesa = 'Erro na SUBMISSÃO DA PROPOSTA'
            ultimo_status.save()
    except Exception as e:
        error_message = f'Ocorreu um erro ao aprovar o contrato: {str(e)}'
        logging.error(error_message)


@transaction.atomic
def status_aprovar_contrato(
    request, contrato, produto, primeiro_status, segundo_status
):
    user = None
    if request:
        user = UserProfile.objects.filter(identifier=request.user.identifier).first()

    if user:
        StatusContrato.objects.create(
            contrato=contrato,
            nome=primeiro_status,
            descricao_mesa='Contrato Submetido Para a QITECH',
            created_by=user,
        )
        produto.refresh_from_db()
        produto.status = segundo_status
        produto.dt_envio_proposta_CIP = datetime.now()
        produto.save(update_fields=['status', 'dt_envio_proposta_CIP'])
        produto.refresh_from_db()
        user = UserProfile.objects.get(identifier=request.user.identifier)
        StatusContrato.objects.create(
            contrato=contrato,
            nome=segundo_status,
            created_by=user,
        )
        contrato.status = EnumContratoStatus.EM_AVERBACAO
        contrato.save(update_fields=['status'])
    else:
        StatusContrato.objects.create(
            contrato=contrato,
            nome=primeiro_status,
            descricao_mesa='Contrato Submetido Para a QITECH',
        )
        produto.refresh_from_db()
        produto.status = segundo_status
        produto.dt_envio_proposta_CIP = datetime.now()
        produto.save(update_fields=['status', 'dt_envio_proposta_CIP'])
        produto.refresh_from_db()
        StatusContrato.objects.create(
            contrato=contrato,
            nome=segundo_status,
        )
        contrato.status = EnumContratoStatus.EM_AVERBACAO
        contrato.save(update_fields=['status'])


def botao_aprovar_contrato(request):
    """Botão para aprovação do contrato manualmente"""
    id_contrato = request.GET.get('id_contrato')
    contrato = get_object_or_404(Contrato, id=id_contrato)

    return approve_contract_automatic(contrato, request)


def approve_contract_automatic(contrato, request=None):
    token_contrato = contrato.token_contrato

    try:
        if contrato.tipo_produto in [
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ]:
            contrato_produto = Portabilidade.objects.get(contrato=contrato)
        elif contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE:
            contrato_produto = MargemLivre.objects.get(contrato=contrato)
        else:
            if request:
                # Retorna um erro caso outro tipo de contrato tente rodar esta funcionalidade.
                messages.error(
                    request,
                    'Esse tipo de contrato não pode executar esta ação.',
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')
            else:
                return
        # Verificar se o contrato foi assinado
        if not contrato.contrato_assinado:
            if request:
                messages.warning(
                    request, 'Contrato não assinado! Assine o contrato primeiro'
                )
                return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')
            else:
                return

        # Verificar se o token do contrato existe
        if not token_contrato:
            if request:
                messages.error(request, 'Contrato não encontrado')
                return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')
            else:
                return

        # Enviar documentos para a API
        resposta_documentos = qitech_apis.API_qitech_documentos(token_contrato)
        if not resposta_documentos:
            contrato_produto.sucesso_documentos_linkados = False
            contrato_produto.motivo_documentos_linkados = (
                'Erro na QITECH ao conectar os documentos na PROPOSTA (400)'
            )
            contrato_produto.save()
            if request:
                messages.error(request, 'Erro ao realizar o envio de documentos')
                return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')
            else:
                return

        # Enviar assinatura para a API
        resposta_assinatura = qitech_apis.API_qitech_envio_assinatura(token_contrato)
        if not resposta_assinatura:
            if contrato.tipo_produto in [
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.MARGEM_LIVRE,
            ]:
                # Caso o produto seja PORTABILIDADE ou MARGEM_LIVRE, salva o status normal
                contrato_produto.sucesso_envio_assinatura = False
                contrato_produto.motivo_envio_assinatura = (
                    'Erro na API de envio de Assinatura QITECH (400)'
                )
                contrato_produto.save()

            # Em PORT+REFIN retorna apenas o erro, pois a mensagem de motivo_envio e sucesso_envio foram definidas na
            # função API_qitech_envio_assinatura
            if request:
                messages.error(request, 'Erro ao realizar a assinatura')
                return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')
            else:
                return

        contrato_produto.sucesso_envio_assinatura = True
        contrato_produto.save()

        contrato_produto.sucesso_documentos_linkados = True
        contrato_produto.save()

        if contrato.tipo_produto in [
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ]:
            if SubmitFinancialPortabilityProposal(contract=contrato).execute():
                status_aprovar_contrato(
                    request,
                    contrato,
                    contrato_produto,
                    ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
                    ContractStatus.AGUARDA_RETORNO_SALDO.value,
                )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refinanciamento = Refinanciamento.objects.get(contrato=contrato)
                    refinanciamento.status = (
                        ContractStatus.AGUARDANDO_FINALIZAR_PORT.value
                    )
                    refinanciamento.save()
                if request:
                    messages.success(
                        request, 'Assinado com Sucesso - Documentos Enviados'
                    )
                if request:
                    user = request.user
                else:
                    user = UserProfile.objects.get(identifier='00000000099')
                # Caso seja um contrato principal, então envia para os outros contratos a mesma requisição
                if contrato.is_main_proposal:
                    for secondary_contract in get_secondary_contracts(
                        main_contract=contrato,
                    ):
                        approve_portability_contract.apply_async(
                            args=[
                                secondary_contract.id,
                                user.id,
                            ]
                        )

            else:
                if request:
                    messages.error(
                        request,
                        'Não foi assinado nem aprovado erro na SUBMISSÃO DA PROPOSTA',
                    )
        elif contrato.tipo_produto is EnumTipoProduto.MARGEM_LIVRE:
            status_aprovar_contrato(
                request,
                contrato,
                contrato_produto,
                ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
                ContractStatus.INT_AGUARDA_AVERBACAO.value,
            )
            if request:
                messages.success(request, 'Assinado com Sucesso - Documentos Enviados')
    except Exception as e:
        msg = 'Ocorreu um erro ao aprovar o contrato'
        logging.exception(msg)
        logging.error(f'{msg}: {e}')
        if request:
            messages.error(request, f'{msg}.')

    if request:
        return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')


def cancel_contract(contract: Contrato):
    """
    Defines contract status as canceled
    Args:
        contract: Contract to be updated

    """
    contract.status = EnumContratoStatus.CANCELADO
    contract.save()


def deny_product(product):
    """
    Defines product status as denied.
    Could be any product e.g.
     - Portabilidade,
     - Refinanciamento,
     - CartaoBeneficio
     - etc...
    Args:
        product: Product to be updated

    """
    product.status = ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value
    product.save()


def create_status_contract(
    user,
    contrato,
    observacao,
    name,
):
    StatusContrato.objects.create(
        contrato=contrato,
        nome=name,
        created_by=user,
        descricao_mesa=observacao,
    )


def cancel_contract_and_product(
    user,
    contract,
    product,
    note,
):
    """
    Cancel contract and product.
    Args:
        user: User instance from request
        contract: Contrato instance
        product: Product instance [Portabilidade, Refinanciamento, CartaoBeneficio, etc...]
        note: Note to be saved in StatusContract

    """
    cancel_contract(contract)
    deny_product(product)
    create_status_contract(
        user,
        contract,
        note,
        ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
    )


def botao_recusar_contrato(request):
    id_contrato = request.GET.get('id_contrato')
    observacao = request.POST.get('motivo_recusa')
    # Obter o contrato ou retornar uma resposta HTTP 404 se não encontrado
    contrato = get_object_or_404(Contrato, id=id_contrato)
    return refuse_contract(contrato, observacao, request)


def refuse_contract(contrato, observacao, request=None):
    cliente = contrato.cliente
    if request:
        user = request.user
    else:
        user = UserProfile.objects.get(identifier='00000000099')

    try:
        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            contrato_portabilidade = Portabilidade.objects.get(contrato=contrato)
            if (
                contrato_portabilidade.chave_proposta
                and (RefuseProposalFinancialPortability(contrato=contrato).execute())
                or not contrato_portabilidade.chave_proposta
            ):
                cancel_contract_and_product(
                    user, contrato, contrato_portabilidade, observacao
                )
                if request:
                    messages.success(
                        request, f'Contrato {contrato.id} - {cliente} REPROVADO.'
                    )
            else:
                if request:
                    messages.error(
                        request,
                        'Ocorreu um erro na chamada da API \n Valide na aba Portabilidade(RESPOSTAS APIS QITECH)',
                    )
        elif contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            portabilidade = Portabilidade.objects.get(contrato=contrato)
            refinanciamento = Refinanciamento.objects.get(contrato=contrato)
            # A segunda cláusula do OR só roda, se a primeira for Falsa.
            # Ou seja, só vai rodar a função de recusa_proposta se ele possuir chave_proposta.
            if not portabilidade.chave_proposta:
                cancel_contract_and_product(user, contrato, portabilidade, observacao)
                deny_product(refinanciamento)

                if request:
                    messages.success(
                        request, f'Contrato {contrato.id} - {cliente} REPROVADO.'
                    )

            elif RefuseProposalFinancialPortability(contrato=contrato).execute():
                cancel_contract_and_product(
                    user,
                    contrato,
                    portabilidade,
                    observacao,
                )
                deny_product(refinanciamento)
                if request:
                    messages.success(
                        request, f'Contrato {contrato.id} - {cliente} REPROVADO.'
                    )

            else:
                if request:
                    messages.error(
                        request,
                        'Ocorreu um erro na chamada da API \n Valide na aba Portabilidade(RESPOSTAS APIS QITECH)',
                    )
        elif contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            margem_livre = MargemLivre.objects.get(contrato=contrato)
            if (
                not margem_livre.chave_proposta
                or margem_livre.chave_proposta
                and RefuseProposalFinancialFreeMargin(contrato).execute()
            ):
                cancel_contract_and_product(user, contrato, margem_livre, observacao)
                if request:
                    messages.success(
                        request, f'Contrato {contrato.id} - {cliente} REPROVADO.'
                    )
            else:
                messages.error(
                    request,
                    'Ocorreu um erro na chamada da API \n Valide na aba Margem Livre(RESPOSTAS APIS QITECH)',
                )

        if (
            contrato.tipo_produto
            in [
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ]
            and contrato.is_main_proposal
        ):
            for secondary_contract in get_secondary_contracts(
                main_contract=contrato,
            ):
                deny_portability_contract.apply_async(
                    args=[
                        secondary_contract.id,
                        user.id,
                        observacao,
                    ]
                )

    except Exception as e:
        logging.error(f'Ocorreu um erro ao recusar o contrato: {e}')
        if request:
            messages.error(request, 'Ocorreu um erro ao recusar o contrato.')

    if request:
        return HttpResponseRedirect(f'/admin/contract/contrato/{contrato.id}')


def put_product_on_hold(product):
    """
    Put product on hold for corban validations.
    Args:
        product: Product instance [Portabilidade, Refinanciamento, CartaoBeneficio, etc...]

    """
    product.status = ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value
    product.save()


def update_issue_button(request: WSGIRequest):
    from contract.services.payment.endorsement_correction import EndorsementCorrection

    contract_id: str = request.GET.get('id_contrato')
    contract: Contrato = Contrato.objects.get(id=contract_id)
    client: Cliente = contract.cliente
    dadosin100: DadosIn100 = client.cliente_in100.first()
    bank_data: DadosBancarios = get_client_bank_data(client=contract.cliente)
    try:
        pendency_reason = PendencyReasonEnum(request.GET.get('motivo'))
    except ValueError:
        messages.error(
            request, message='Motivo da pendência não valido para atualização'
        )
        return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')
    try:
        agency = request.POST.get('agencia', '').strip()
        account_number = request.POST.get('conta_numero', '').strip()
        state_uf = request.POST.get('uf', '').strip()
        customer_name = request.POST.get('nome_cliente', '').strip()
        benefit_number = request.POST.get('numero_beneficio', '').strip()
        bank_number = request.POST.get('numero_banco', '').strip()

        # TODO: Refactor fix DRY
        error_message = (
            'Não foi possível atualizar os dados pendentes, '
            'os dados não podem ser iguais aos já cadastrados ou vazios.'
        )
        if pendency_reason == PendencyReasonEnum.BANK_DETAILS:
            bank_data.conta_agencia = agency
            bank_data.conta_numero = account_number
            bank_data.save(update_fields=['conta_agencia', 'conta_numero'])

        elif pendency_reason == PendencyReasonEnum.BANK_NUMBER:
            validate_data = bool(
                str(bank_data.conta_banco) != str(bank_number) and bank_number
            )
            if not validate_data:
                messages.error(request, message=error_message)
                return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')

            bank_data.conta_banco = bank_number
            bank_data.save(update_fields=['conta_banco'])

        elif pendency_reason == PendencyReasonEnum.CLIENT_NAME:
            nome_cliente = str(client.nome_cliente).strip()
            validate_data = bool(nome_cliente != str(customer_name) and customer_name)
            if not validate_data:
                messages.error(request, message=error_message)
                return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')

            client.nome_cliente = customer_name
            client.save(update_fields=['nome_cliente'])
        elif pendency_reason == PendencyReasonEnum.STATE:
            validate_data = bool(str(client.endereco_uf) != str(state_uf) and state_uf)
            if not validate_data:
                messages.error(request, message=error_message)
                return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')

            client.endereco_uf = state_uf
            client.save(update_fields=['endereco_uf'])
        elif pendency_reason == PendencyReasonEnum.BENEFIT_NUMBER:
            # validate_data = bool(
            #     str(dadosin100.numero_beneficio) != str(benefit_number)
            #     and benefit_number
            # )
            # if not validate_data:
            #     messages.error(request, message=error_message)
            #     return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')

            dadosin100.numero_beneficio = benefit_number
            dadosin100.save(update_fields=['numero_beneficio'])

        portability: Portabilidade = contract.contrato_portabilidade.filter(
            contrato=contract
        ).first()
        refinancing: Refinanciamento = contract.contrato_refinanciamento.filter(
            contrato=contract
        ).first()
        free_margin: MargemLivre = contract.contrato_margem_livre.filter(
            contrato=contract
        ).first()

        # Se o status original for igual ao atual
        if free_margin:
            EndorsementCorrection(
                product=free_margin,
                type_correction=pendency_reason,
                request_type='new_credit',
            ).execute()
            free_margin.status = ContractStatus.INT_AGUARDA_AVERBACAO.value
            free_margin.save()
            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                descricao_mesa='Os dados pendentes foram atualizados com a QiTech',
                created_by=UserProfile.objects.get(identifier=request.user.identifier),
            )
        if portability and not refinancing:
            portability.numero_beneficio = benefit_number
            portability.save()
            portability.refresh_from_db()
            contract.numero_beneficio = benefit_number
            contract.save()
            EndorsementCorrection(
                product=portability,
                type_correction=pendency_reason,
                request_type='portability',
            ).execute()
            portability.status = ContractStatus.INT_AGUARDA_AVERBACAO.value
            portability.save()
            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                descricao_mesa='Os dados pendentes foram atualizados com a QiTech',
                created_by=UserProfile.objects.get(identifier=request.user.identifier),
            )
        if portability and refinancing:
            portability.numero_beneficio = benefit_number
            portability.save()
            portability.refresh_from_db()
            contract.numero_beneficio = benefit_number
            contract.save()
            if portability.status == ContractStatus.INT_AJUSTE_AVERBACAO.value:
                EndorsementCorrection(
                    product=portability,
                    type_correction=pendency_reason,
                    request_type='portability',
                ).execute()
                portability.status = ContractStatus.INT_AGUARDA_AVERBACAO.value
                portability.save()
                StatusContrato.objects.create(
                    contrato=contract,
                    nome=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                    descricao_mesa='Os dados pendentes foram atualizados com a QiTech',
                    created_by=UserProfile.objects.get(
                        identifier=request.user.identifier
                    ),
                )
            if refinancing.status == ContractStatus.INT_AJUSTE_AVERBACAO.value:
                EndorsementCorrection(
                    product=refinancing,
                    type_correction=pendency_reason,
                    request_type='refinancing',
                ).execute()
                refinancing.status = ContractStatus.INT_AGUARDA_AVERBACAO.value
                refinancing.save()
                StatusContrato.objects.create(
                    contrato=contract,
                    nome=ContractStatus.INT_AGUARDA_AVERBACAO.value,
                    descricao_mesa='Os dados pendentes foram atualizados com a QiTech',
                    created_by=UserProfile.objects.get(
                        identifier=request.user.identifier
                    ),
                )

        messages.success(request, message='AVERBAÇÃO reapresentada com sucesso')
        return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')
    except Exception as e:
        messages.error(request, message=f'Não foi possivel corrigir os dados {e}')
        return HttpResponseRedirect(f'/admin/contract/contrato/{contract_id}')


def botao_pendenciar_contrato(request):
    """
    View for the functionality of the PEND CONTRACT button.

    Used only in the contrato_pendente.html file, whenever the button is enabled.

    For the products:
    - Portability
    - Free Margin
    - Portability + Refinancing
    Args:
        request: WSGI Request

    Returns: HttpResponseRedirect

    """
    id_contrato = request.GET.get('id_contrato')
    observacao = request.POST.get('motivo_pendencia')

    # Obter o contrato ou retornar uma resposta HTTP 404 se não encontrado
    contrato = get_object_or_404(Contrato, id=id_contrato)
    cliente = contrato.cliente

    if (
        not contrato.selfie_enviada
        and not AnexoContrato.objects.filter(tipo_anexo=EnumTipoAnexo.SELFIE).exists()
    ):
        messages.error(
            request,
            'Não foi possível pendenciar o contrato pois o contrato ainda não foi formalizado.',
        )
        return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')

    # !TODO Refatorar para receber uma LISTA de pendências ao invés de apenas chaves distintas
    pendente_numero_RG = request.POST.get('pendente_rg')
    pendente_dt_expedicao_RG = request.POST.get('pendente_dt_expedicao_rg')
    pendente_dt_nascimento = request.POST.get('pendente_dt_nascimento')
    pendente_sexo = request.POST.get('pendente_sexo')
    pendente_nome = request.POST.get('pendente_nome')
    pendente_documento = request.POST.get('pendente_documento')
    pendente_selfie = request.POST.get('pendente_selfie')

    try:
        conteudo = ''
        if pendente_numero_RG:
            conteudo += 'rg, '
        if pendente_dt_expedicao_RG:
            conteudo += 'dt_expedicao_rg, '
        if pendente_dt_nascimento:
            conteudo += 'dt_nascimento, '
        if pendente_sexo:
            conteudo += 'sexo, '
        if pendente_nome:
            conteudo += 'nome_cliente, '
        if pendente_documento:
            contrato.pendente_documento = True
        if pendente_selfie:
            contrato.selfie_pendente = True
            mensagem = (
                f'{cliente.nome_cliente}, sua proposta foi pendenciada e será necessário regularizá-la '
                f'através do link: {contrato.url_formalizacao}'
            )
            zenvia_sms(cliente.nu_cpf, cliente.telefone_celular, mensagem)
        contrato.campos_pendentes = conteudo
        contrato.status = EnumContratoStatus.MESA
        contrato.save()

        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            put_product_on_hold(Portabilidade.objects.get(contrato=contrato))
        elif contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            put_product_on_hold(MargemLivre.objects.get(contrato=contrato))
        elif contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            put_product_on_hold(Portabilidade.objects.get(contrato=contrato))
            put_product_on_hold(Refinanciamento.objects.get(contrato=contrato))

        StatusContrato.objects.create(
            contrato=contrato,
            nome=ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value,
            created_by=request.user,
            descricao_mesa=observacao,
        )
        messages.warning(request, f'Contrato {id_contrato} - {cliente} PENDENCIADO.')

    except Exception as e:
        # Log the error and display a message to the user
        logging.error(f'Ocorreu um erro ao pendenciar o contrato: {e}')
        messages.error(request, 'Ocorreu um erro ao pendenciar o contrato.')

    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


class ValidarCPFReceitaCorban(GenericAPIView):
    def patch(self, request):
        token_envelope = request.data['token']
        numero_cpf = request.data['cpf']
        try:
            contrato = Contrato.objects.filter(token_envelope=token_envelope).first()
            consulta_bureau = consulta_regras_hub_receita_corban(numero_cpf, contrato)
            consulta_regras = consulta_bureau['regras']
            contratos = Contrato.objects.filter(token_envelope=token_envelope)
            for contrato in contratos:
                contrato_portabilidade = Portabilidade.objects.get(contrato=contrato)
                error, erro_restritivo = self.process_regras_contrato(
                    contrato, consulta_regras, contrato_portabilidade
                )
                self.save_contract_status(
                    contrato, error, erro_restritivo, contrato_portabilidade
                )

                if not error and not erro_restritivo:
                    contrato_portabilidade.status = (
                        ContractStatus.ANALISE_DE_CREDITO.value
                    )
                    contrato_portabilidade.save()
                    StatusContrato.objects.create(
                        contrato=contrato, nome=ContractStatus.ANALISE_DE_CREDITO.value
                    )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.get(contrato=contrato)
                    port = Portabilidade.objects.get(contrato=contrato)
                    port.refresh_from_db()
                    refin.status = port.status
                    refin.save(update_fields=['status'])

            return Response(
                {
                    'msg': 'Contratos Validados',
                },
                status=HTTP_200_OK,
            )
        except Exception as e:
            logger.exception(
                f'Contrato não Encontrado em nosso sistema (ValidarCPFReceitaCorban): {e}'
            )
            return Response(
                {'msg': 'Contrato não Encontrado em nosso sistema.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def process_regras_contrato(
        self, contrato, consulta_regras, contrato_portabilidade
    ):
        error = False
        erro_restritivo = False
        msg = ''
        consulta_regras = exclude_all_check_rules(consulta_regras)
        for elemento in consulta_regras:
            descricao = elemento['descricao']
            regra_aprovada, restritiva = self.process_regra_aprovada(elemento)
            if not elemento['regra_aprovada']:
                contrato_portabilidade.CPF_dados_divergentes = True
                contrato_portabilidade.save()

            if elemento['regra_aprovada']:
                contrato_portabilidade.CPF_dados_divergentes = False
                contrato_portabilidade.save()

            if ValidacaoContrato.objects.filter(
                contrato=contrato, mensagem_observacao=descricao
            ).exists():
                validar_check = ValidacaoContrato.objects.get(
                    contrato=contrato, mensagem_observacao=descricao
                )

                validar_check.checked = regra_aprovada
                validar_check.retorno_hub = msg
                validar_check.save()
            else:
                ValidacaoContrato.objects.create(
                    contrato=contrato,
                    mensagem_observacao=descricao,
                    checked=regra_aprovada,
                    retorno_hub=msg,
                )

            if restritiva and not regra_aprovada:
                erro_restritivo = True

            if not restritiva and not regra_aprovada:
                error = True

        return error, erro_restritivo

    def process_regra_aprovada(self, elemento):
        regra_aprovada = elemento['regra_aprovada']
        restritiva = elemento['restritiva']
        return regra_aprovada, restritiva

    def save_contract_status(self, contrato, error, erro_restritivo, contrato_status):
        if error:
            ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
            if ultimo_status.nome != ContractStatus.ANALISE_DE_CREDITO.value:
                contrato.status = EnumContratoStatus.MESA
                contrato_status.status = ContractStatus.ANALISE_DE_CREDITO.value
                contrato_status.save()
                StatusContrato.objects.create(
                    contrato=contrato, nome=ContractStatus.ANALISE_DE_CREDITO.value
                )
                if (
                    contrato.tipo_produto
                    in (
                        EnumTipoProduto.PORTABILIDADE,
                        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                    )
                    and contrato_status.CPF_dados_divergentes
                ):
                    contrato.status = EnumContratoStatus.MESA
                    contrato_status.status = (
                        ContractStatus.PENDENTE_DADOS_DIVERGENTES.value
                    )
                    contrato_status.save()
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.PENDENTE_DADOS_DIVERGENTES.value,
                    )

        if erro_restritivo:
            ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
            if ultimo_status.nome != ContractStatus.REPROVADA_POLITICA_INTERNA.value:
                contrato.status = EnumContratoStatus.CANCELADO
                contrato_status.status = ContractStatus.REPROVADA_POLITICA_INTERNA.value
                contrato_status.save()
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                )
        contrato.save()


class ConsultaAutorizacaoIN100(GenericAPIView):
    def post(self, request):
        try:
            cpf = request.data['cpf']
            numero_beneficio = request.data['numero_beneficio']
            cliente = Cliente.objects.filter(nu_cpf=cpf).first()

            in100 = DadosIn100.objects.filter(
                cliente=cliente, numero_beneficio=numero_beneficio
            ).first()
            if in100 and in100.cliente.nu_cpf != cpf:
                return Response(
                    {'Erro': 'Número de benefício incorreto para CPF digitado.'},
                    status=HTTP_400_BAD_REQUEST,
                )

            if in100 is None or not in100.in100_data_autorizacao_:
                parametros_backoffice = ParametrosBackoffice.objects.get(
                    ativo=True, tipoProduto=12
                )

                url = parametros_backoffice.url_formalizacao
                url_formalizacao_longa = (
                    f'{url}/in100/{cliente.nu_cpf_}/{numero_beneficio}'
                )

                url_formalizacao_curta = generate_short_url(
                    long_url=url_formalizacao_longa
                )

                return Response(
                    {
                        'in100_autorizada': False,
                        'link_in100': f'{url_formalizacao_curta}',
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                serializer = IN100Serializer(in100)
                try:
                    serializer_data_copy = serializer.data.copy()
                    serializer = serializer_data_copy
                    if dados_bancarios := DadosBancarios.objects.filter(
                        cliente=cliente, retornado_in100=True
                    ).last():
                        dados_bancarios_data = AutorizacaoDadosBancariosSerializer(
                            dados_bancarios
                        ).data
                        serializer['dados_bancarios'] = dados_bancarios_data
                except Exception:
                    pass
                return Response(serializer)
        except Exception:
            newrelic.agent.notice_error()
            logger.exception('Something wrong with ConsultaAutorizacaoIN100')
            return Response(
                {
                    'Erro': 'Não foi possível realizar a consulta da autorização da IN100'
                },
                status=HTTP_400_BAD_REQUEST,
            )


def aceita_proposta_automatica_qitech_cip(contrato):
    """Aceite da proposta automaticamente"""
    portabilidade = Portabilidade.objects.get(contrato=contrato)
    try:
        validacao_beneficio = valida_beneficio_recalculo(
            contrato=contrato, portabilidade=portabilidade
        )
        if not validacao_beneficio['regra_aprovada']:
            alterar_status(
                contrato,
                portabilidade,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO.value,
                observacao=validacao_beneficio['motivo'],
            )
        else:
            if AcceptProposalFinancialPortability(contract=contrato).execute():
                portabilidade.status = ContractStatus.INT_CONFIRMA_PAGAMENTO.value
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
                    descricao_mesa='Proposta aceita',
                )
                portabilidade.status_ccb = EnumStatusCCB.ACCEPTED.value
                portabilidade.save()
            else:
                ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
                ultimo_status.descricao_mesa = portabilidade.motivo_aceite_proposta
                ultimo_status.save(update_fields=['descricao_mesa'])
    except Exception as e:
        logging.error(f'Ocorreu um erro ao ACEITAR a proposta: {e}')


def aceita_proposta_qitech_cip(request: WSGIRequest):
    """Botão para aceite da proposta manualmente"""
    id_contrato = request.GET.get('id_contrato')

    # Obter o contrato ou retornar uma resposta HTTP 404 se não encontrado
    contrato = get_object_or_404(Contrato, id=id_contrato)
    portabilidade = Portabilidade.objects.get(contrato=contrato)
    usuario = UserProfile.objects.get(identifier=request.user.identifier)

    try:
        validacao_beneficio = valida_beneficio_recalculo(contrato, portabilidade)
        if not validacao_beneficio['regra_aprovada']:
            messages.error(
                request,
                f"Proposta não aceita erro no ACEITE enviado para QITECH\n {validacao_beneficio['motivo']}",
            )
            return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')
        if AcceptProposalFinancialPortability(contract=contrato).execute():
            portabilidade.status = ContractStatus.INT_CONFIRMA_PAGAMENTO.value
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
                created_by=usuario,
            )
            portabilidade.status_ccb = EnumStatusCCB.ACCEPTED.value
            portabilidade.save()
            messages.success(
                request,
                message='Proposta aceita com sucesso ACEITE enviado para QITECH',
            )

        else:
            messages.error(
                request,
                f'Proposta não aceita erro no ACEITE enviado para QITECH\n {portabilidade.motivo_aceite_proposta}',
            )

    except Exception as e:
        # Log the error and display a message to the user
        logging.error(f'Ocorreu um erro ao ACEITAR a proposta: {e}')
        messages.error(request, 'Ocorreu um erro ao ACEITAR a proposta.')

    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


def recusa_proposta_qitech_cip(request):
    """Botão para recusa da proposta manualmente"""
    id_contrato = request.GET.get('id_contrato')

    # Obter o contrato ou retornar uma resposta HTTP 404 se não encontrado
    contrato = get_object_or_404(Contrato, id=id_contrato)
    portabilidade = Portabilidade.objects.get(contrato=contrato)
    usuario = UserProfile.objects.get(identifier=request.user.identifier)
    observacao = request.POST.get('motivo_recusa')
    try:
        RefuseProposalFinancialPortability(contrato=contrato).execute()
        StatusContrato.objects.create(
            contrato=contrato,
            nome=ContractStatus.SALDO_REPROVADO.value,
            created_by=usuario,
            descricao_mesa=observacao,
        )
        portabilidade.status = ContractStatus.REPROVADO.value
        portabilidade.status_ccb = EnumStatusCCB.CANCELED.value
        portabilidade.save(update_fields=['status', 'status_ccb'])

        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            refinancing = Refinanciamento.objects.get(contrato=contrato)
            refinancing.status = ContractStatus.REPROVADO.value
            refinancing.status_ccb = EnumStatusCCB.CANCELED.value
            refinancing.save(update_fields=['status', 'status_ccb'])

        contrato.status = EnumContratoStatus.CANCELADO
        contrato.save(update_fields=['status'])
        messages.success(request=request, message='Proposta RECUSADA COM SUCESSO')
    except Exception:
        logging.exception('Ocorreu um erro ao RECUSAR a proposta.')
        messages.error(
            request=request, message='Ocorreu um erro ao RECUSAR a proposta.'
        )

    return HttpResponseRedirect(f'/admin/contract/contrato/{id_contrato}')


# Api para enviar os parametros de Produtos para verificaçaõ no Front
# TODO: Colocar API mais genérica, fora da URL de portabilidade. Sugestão: "/api/produtos/regras-elegibilidade"
class RegrasElegibilidade(GenericAPIView):
    def get(self, request):
        product_type = request.GET.get('product_type', EnumTipoProduto.PORTABILIDADE)

        try:
            regras_elegibilidade = ParametrosProduto.objects.filter(
                tipoProduto=product_type
            ).first()
            serializer_parametros = DetalheParametrosProdutoSerializer(
                regras_elegibilidade, many=False
            )
            return Response(serializer_parametros.data)

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu nas validações, Contacte um Administrador.'},
                status=HTTP_400_BAD_REQUEST,
            )


class RegrasElegibilidadeEspecies(GenericAPIView):
    def post(self, request):
        try:
            cpf_cliente = request.data['cpf_cliente']
            numero_beneficio = request.data['numero_beneficio']
            if not cpf_cliente:
                return Response(
                    {'Erro': 'CPF do cliente não informado.'},
                    status=HTTP_400_BAD_REQUEST,
                )
            try:
                cliente = Cliente.objects.filter(nu_cpf=cpf_cliente).first()
                in100 = DadosIn100.objects.filter(
                    numero_beneficio=numero_beneficio
                ).last()
                if not in100.retornou_IN100 or not in100.in100_data_autorizacao_:
                    return Response(
                        {
                            'In100 ainda nao retornada sera validado no Final da Originação'
                        },
                        status=HTTP_200_OK,
                    )

                resposta = validar_regra_especie(
                    in100.cd_beneficio_tipo, cliente, numero_beneficio
                )
                return (
                    Response({'Analise Aprovada'}, status=HTTP_200_OK)
                    if resposta['regra_aprovada']
                    else Response(
                        {'Erro': f"{resposta['motivo']}"},
                        status=HTTP_400_BAD_REQUEST,
                    )
                )
            except Exception as e:
                print(e)
                return Response(
                    {'Erro': 'Ocorreu nas validações, Contacte um Administrador.'},
                    status=HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            print(e)
            return Response(
                {'Erro': 'Ocorreu nas validações, Contacte um Administrador.'},
                status=HTTP_400_BAD_REQUEST,
            )


def valida_beneficio_recalculo(
    contrato: Contrato, portabilidade: Portabilidade
) -> dict[str, any]:
    in100 = DadosIn100.objects.filter(
        numero_beneficio=contrato.numero_beneficio
    ).first()
    resposta = {}
    if in100.validacao_in100_recalculo:
        # status = StatusContrato.objects.filter(contrato=contrato).last()
        if not EspecieIN100.objects.filter(
            numero_especie=in100.cd_beneficio_tipo
        ).exists():
            contrato.status = EnumContratoStatus.CANCELADO
            contrato.save(update_fields=['status'])
            # portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
            portabilidade.status = ContractStatus.REPROVADO.value
            portabilidade.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.REPROVADO.value,
                descricao_mesa=f'{in100.cd_beneficio_tipo} - Especie não cadastrada',
            )
            resposta['regra_aprovada'] = False
            resposta['motivo'] = 'Especie Não Encontrada'
            RefuseProposalFinancialPortability(contrato=contrato).execute()

        elif in100.situacao_beneficio in ('INELEGÍVEL', 'BLOQUEADO', 'BLOQUEADA'):
            contrato.status = EnumContratoStatus.CANCELADO
            contrato.save(update_fields=['status'])

            portabilidade.status = ContractStatus.REPROVADO.value
            portabilidade.save(update_fields=['status'])
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.REPROVADO.value,
                descricao_mesa='Beneficio bloqueado ou cessado',
            )
            resposta['regra_aprovada'] = False
            resposta['motivo'] = 'Beneficio bloqueado ou cessado'
            RefuseProposalFinancialPortability(contrato=contrato).execute()
        else:
            resposta_validacao = validar_regra_especie(
                numero_especie=in100.cd_beneficio_tipo,
                cliente=contrato.cliente,
                numero_beneficio=contrato.numero_beneficio,
            )
            if not resposta_validacao['regra_aprovada']:
                resposta['regra_aprovada'] = False
                resposta['motivo'] = resposta_validacao['motivo']
            else:
                resposta_morte = validacao_regra_morte(contrato=contrato)
                if not resposta_morte['regra_aprovada']:
                    resposta['regra_aprovada'] = False
                    resposta['motivo'] = resposta_morte['motivo']
                else:
                    resposta['regra_aprovada'] = True
    else:
        resposta['regra_aprovada'] = False
        resposta['motivo'] = 'IN100 não retornada no recalculo ainda'
    return resposta


def consulta_beneficio_in100(request):
    """Botão para realizar uma nova consulta à IN100"""

    id_cliente = request.GET.get('id_cliente')
    cliente = get_object_or_404(Cliente, id=id_cliente)
    dados_in100 = DadosIn100.objects.filter(cliente=cliente).last()
    numero_beneficio = dados_in100.numero_beneficio
    try:
        consulta_beneficio_in100_portabilidade(cliente, numero_beneficio, dados_in100)
        messages.success(request, 'A Consulta da IN100 foi realizada com Sucesso')
    except Exception as e:
        logging.error(f'Ocorreu um erro ao realizar a consulta da IN100: {e}')
        messages.error(request, 'Ocorreu um erro ao realizar a consulta da IN100.')

    return HttpResponseRedirect(f'/admin/core/cliente/{id_cliente}')
