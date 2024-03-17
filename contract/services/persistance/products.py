import logging

from django.utils import timezone
from rest_framework.exceptions import ValidationError

import handlers.webhook_qitech as apis_qitech
from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
    SubmitFinancialPortabilityProposal,
)
from contract.services.persistance.contract import (
    create_contract_status,
    update_contract_status,
)
from custom_auth.models import UserProfile
from handlers.submete_proposta_portabilidade import (
    refuse_product_proposal_qitech,
)


def update_product_status(
    product,
    status=ContractStatus.REPROVADO.value,
):
    product.status = status
    product.save(update_fields=['status'])


class SubmitPortabilityDocumentsAndSignature:
    """
    AFFECTS -> Portability and Portability+Refinancing product.
    Send documents and signatures to QI Tech.
    Also sends pending_response after successful documents and signature submit.
    """

    def __init__(
        self,
        contract: Contrato,
        product: Portabilidade,
        user: UserProfile,
    ):
        self.contract = contract
        self.product = product
        self.user = user

    def send_documents_qitech(self):
        resposta_documentos = apis_qitech.API_qitech_documentos(
            self.contract.token_contrato
        )
        if not resposta_documentos:
            self.update_failed_documents_status()
            error_message = (
                f' [{self.contract.id}]-  Erro ao realizar o envio de documentos'
            )
            logging.error(error_message)
            raise ValidationError(error_message)

    def send_signature_qitech(self):
        signature_response = apis_qitech.API_qitech_envio_assinatura(
            self.contract.token_contrato
        )
        if not signature_response:
            # Caso o produto seja PORTABILIDADE ou MARGEM_LIVRE, salva o status normal
            if self.contract.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                self.update_failed_signature_status()
            # Em PORT+REFIN retorna apenas o erro, pois a mensagem de motivo_envio e sucesso_envio foram definidas na
            # função API_qitech_envio_assinatura
            logging.error(f' [{self.contract.id}]- Erro ao realizar a assinatura')
            raise ValidationError(
                f' [{self.contract.id}]- Erro ao realizar o envio de documentos'
            )

    def update_failed_documents_status(self):
        self.product.sucesso_envio_assinatura = False
        self.product.motivo_envio_assinatura = (
            'Erro na API de envio de Assinatura QITECH (400)'
        )
        self.product.save(
            update_fields=[
                'sucesso_envio_assinatura',
                'motivo_envio_assinatura',
            ]
        )

    def update_failed_signature_status(self):
        self.product.sucesso_envio_assinatura = False
        self.product.motivo_envio_assinatura = (
            'Erro na API de envio de Assinatura QITECH (400)'
        )
        self.product.save(
            update_fields=[
                'sucesso_envio_assinatura',
                'motivo_envio_assinatura',
            ]
        )

    # Em PORT+
    def update_successful_signature_status(self):
        self.product.sucesso_envio_assinatura = True
        self.product.sucesso_documentos_linkados = True
        self.product.save(
            update_fields=[
                'sucesso_envio_assinatura',
                'sucesso_documentos_linkados',
            ]
        )

    def create_successful_contract_statuses(self):
        self.product.status = ContractStatus.AGUARDA_RETORNO_SALDO.value
        self.product.dt_envio_proposta_CIP = timezone.localtime()
        self.product.save(
            update_fields=[
                'status',
                'dt_envio_proposta_CIP',
            ],
        )
        self.contract.status = EnumContratoStatus.EM_AVERBACAO
        self.contract.save(
            update_fields=[
                'status',
            ],
        )
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
            descricao_mesa='Contrato Submetido Para a QITECH',
            created_by=self.user,
        )
        StatusContrato.objects.create(
            contrato=self.contract,
            nome=ContractStatus.AGUARDA_RETORNO_SALDO.value,
            created_by=self.user,
        )

    def update_successful_status(self):
        update_product_status(
            self.product,
            ContractStatus.APROVADA_MESA_DE_FORMALIZACAO.value,
        )
        self.create_successful_contract_statuses()
        if self.contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            Refinanciamento.objects.update_or_create(
                contrato=self.contract,
                defaults={'status': ContractStatus.AGUARDANDO_FINALIZAR_PORT.value},
            )

    def submit_pending_response_proposal(self):
        if SubmitFinancialPortabilityProposal(contract=self.contract).execute():
            self.update_successful_status()
        else:
            error_message = (
                f'[{self.contract.id}]- Erro ao submeter a proposta (pending_response)'
            )
            logging.error(error_message)
            raise ValidationError(error_message)

    def validate_contract(self):
        error_message = ''
        if not self.contract.token_contrato:
            error_message = f'[{self.contract.id}]- Erro ao realizar a aprovação pois não existe token_contrato'
        elif not self.contract.contrato_assinado:
            error_message = f'[{self.contract.id}]- Erro ao realizar o envio de documentos pois o documento não foi assinado!'

        if error_message:
            logging.error(error_message)
            raise ValidationError(error_message)

    def execute(self):
        self.validate_contract()
        self.send_documents_qitech()
        self.send_signature_qitech()
        self.submit_pending_response_proposal()


class DenyPortabilityContract:
    """
    Denies Portability contract and send to QITech if needed.
    """

    def __init__(
        self, contract: Contrato, user: UserProfile, product: Portabilidade, reason: str
    ):
        self.contract = contract
        self.product = product
        self.user = user
        self.client = self.contract.cliente
        self.reason = reason

    def deny_contract(self):
        update_contract_status(
            self.contract,
            status=EnumContratoStatus.CANCELADO,
        )
        update_product_status(
            self.product,
            ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
        )
        create_contract_status(
            self.contract,
            self.reason,
            ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
            self.user,
        )
        logging.info(f'Contrato {self.contract.id} - {self.client} REPROVADO.')

    def execute(self):
        if (
            not self.product.chave_proposta
            or RefuseProposalFinancialPortability(contrato=self.contract).execute()
        ):
            self.deny_contract()
        else:
            logging.error(
                'Ocorreu um erro na chamada da API \n Valide na aba Portabilidade(RESPOSTAS APIS QITECH)',
            )


class DenyPortabilityRefinancingContract(DenyPortabilityContract):
    """
    Deny and send to
    """

    def __init__(
        self,
        contract: Contrato,
        user: UserProfile,
        product: Portabilidade,
        refinancing: Refinanciamento,
        reason: str,
    ):
        super().__init__(contract, user, product, reason)
        self.refinancing = refinancing

    def deny_contract(self):
        super().deny_contract()
        update_product_status(
            self.refinancing,
            ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
        )

    def execute(self):
        # A segunda cláusula do OR só roda, se a primeira for Falsa.
        # Ou seja, só vai rodar a função de recusa_proposta se ele possuir chave_proposta.
        if not self.product.chave_proposta or refuse_product_proposal_qitech(
            contract=self.contract,
            product=self.product,
        ):
            self.deny_contract()
        else:
            logging.error(
                'Ocorreu um erro na chamada da API \n Valide na aba Portabilidade(RESPOSTAS APIS QITECH)',
            )
