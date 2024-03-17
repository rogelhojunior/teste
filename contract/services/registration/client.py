import logging

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_400_BAD_REQUEST,
)

from contract.constants import EnumContratoStatus, EnumTipoProduto, STATUS_REPROVADOS
from contract.models.contratos import (
    Contrato,
    Portabilidade,
    MargemLivre,
    Refinanciamento,
)
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core.models import Cliente
from core.utils import exclude_all_check_rules
from documentscopy.services import BPOProcessor
from handlers.consultas import consulta_regras_hub_cliente
from handlers.contrato import get_contract_reproved_status


def can_create_client_with_cellphone(
    cellphone: str,
) -> bool:
    """
    Validates if a new client with given cellphone can be created, based on contracts.

    Affects following products:
    - Portability
    - Portability and Refinancing
    - Free margin

    Code for counting the number of active clients in the system based on specific criteria.

    Args:
        cellphone (str): The phone number to be checked.

    Returns:
        bool: A bool object with True if a client with received cellphone can be created.
    """
    max_clients_with_same_phone: int = 2
    ignored_status: tuple = get_contract_reproved_status()

    clients = Cliente.objects.filter(telefone_celular=cellphone)
    if clients.count() >= max_clients_with_same_phone:
        active_clients: int = 0
        for client in clients:
            is_client_active: bool = (
                Contrato.objects.filter(
                    cliente=client,
                    tipo_produto__in=[
                        EnumTipoProduto.PORTABILIDADE,
                        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                        EnumTipoProduto.MARGEM_LIVRE,
                    ],
                )
                .exclude(
                    Q(status=EnumContratoStatus.CANCELADO)
                    | Q(contrato_portabilidade__status__in=ignored_status)
                    | Q(contrato_margem_livre__status__in=ignored_status)
                )
                .exists()
            )
            active_clients += 1 if is_client_active else 0
        return active_clients < max_clients_with_same_phone
    return True


class ValidateClientFormalization:
    def __init__(self, token_envelope: str, cpf: str):
        self.token_envelope = token_envelope
        self.cpf = cpf

    def process_regra_aprovada(self, elemento: dict):
        return elemento['regra_aprovada'], elemento['restritiva']

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

    def validate_contracts(self):
        try:
            contrato = Contrato.objects.filter(
                token_envelope=self.token_envelope
            ).first()
            consulta_bureau = consulta_regras_hub_cliente(self.cpf, contrato)
            consulta_regras = consulta_bureau['regras']
            contratos = Contrato.objects.filter(token_envelope=self.token_envelope)
            for contrato in contratos:
                if not StatusContrato.objects.filter(
                    contrato=contrato,
                    nome__in=STATUS_REPROVADOS,
                ).exists():
                    if contrato.tipo_produto in {
                        EnumTipoProduto.PORTABILIDADE,
                        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                    }:
                        contrato_produto = Portabilidade.objects.get(contrato=contrato)
                    elif contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                        contrato_produto = MargemLivre.objects.get(contrato=contrato)
                    else:
                        raise NotImplementedError(
                            'Tipo de contrato do envelope inválido!!'
                        )
                    error, erro_restritivo = self.process_regras_contrato(
                        contrato, consulta_regras, contrato_produto
                    )
                    if contrato.is_main_proposal and not erro_restritivo:
                        processor = BPOProcessor(contrato, contrato_produto)

                        if processor.bpo is not None:
                            return

                    self.save_contract_status(
                        contrato, error, erro_restritivo, contrato_produto
                    )

                    if not erro_restritivo:
                        # Caso seja a proposta principal, coloca como checagem mesa corban
                        # Caso contrário, coloca AGUARDA_FINALIZACAO_PROPOSTA_PRINCIPAL
                        if contrato.is_main_proposal:
                            corban = contrato.corban

                            proposal_status = (
                                ContractStatus.CHECAGEM_MESA_CORBAN.value
                                if corban and corban.mesa_corban
                                else ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                            )
                        else:
                            proposal_status = ContractStatus.AGUARDA_FINALIZACAO_PROPOSTA_PRINCIPAL.value
                        contrato_produto.status = proposal_status
                        contrato_produto.save()
                        StatusContrato.objects.create(
                            contrato=contrato,
                            nome=proposal_status,
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
        except Exception as e:
            logging.exception(
                f'Houve um erro ao processar a validação do cliente validar o cliente: {e}'
            )
            raise e

    def process_request(self):
        try:
            self.validate_contracts()
            return Response(
                {
                    'msg': 'Contratos Validados',
                },
                status=HTTP_200_OK,
            )
        except Contrato.DoesNotExist:
            return Response(
                {'msg': 'Contrato não encontrado'},
                status=HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logging.exception(
                f'Envelope: ({self.token_envelope}) - Erro ao processar os contratos {e}',
                exc_info=True,
            )
            return Response(
                {'msg': 'Houve um erro ao processar os contratos.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )
