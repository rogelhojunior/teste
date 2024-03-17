from dataclasses import asdict
from datetime import datetime
import logging
import requests
from django.conf import settings
from contract.constants import EnumContratoStatus

from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    SaqueComplementar,
    RetornoSaque,
)
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.services.payment.banksoft_adapter import BanksoftAdapter
from contract.services.payment.schemas import PaymentRequestDTO
from core.models.bancos_brasileiros import BancosBrasileiros
from core.models.cliente import Cliente, ClienteCartaoBeneficio, DadosBancarios
from core.models.parametros_backoffice import ParametrosBackoffice
from core.utils import alterar_status
from custom_auth.models import UserProfile
from handlers.brb import envio_dossie, retorno_saque, transferencia_saque
from handlers.dock_formalizacao import (
    ajustes_financeiros,
    lancamento_saque_parcelado_fatura,
)

logger = logging.getLogger('digitacao')


class PaymentManager:
    """
    Manages payment processing across different payment providers.

    This class abstracts the complexity of interacting with various payment providers
    and offers a unified interface to process payments. It determines the appropriate
    payment provider based on the system configuration and delegates the payment
    processing to the corresponding service.

    Attributes:
        payment_provider (str): The name of the payment provider, which is determined
                                from the system settings (e.g., 'PINE', 'BRB', 'DIGIMAIS').

    Methods:
        process_payment(client): Processes the payment for the given contract
                                           and client, using the appropriate payment
                                           provider.
    """

    def __init__(
        self,
        contract: Contrato,
        user: UserProfile = None,
        benefit_card: CartaoBeneficio = None,
        contrato_saque: SaqueComplementar = None,
    ):
        self.payment_provider = settings.ORIGIN_CLIENT
        self.cognito_username = settings.COGNITO_USERNAME
        self.cognito_password = settings.COGNITO_PASSWORD
        self.base_url = settings.WHITE_PAYMENTS_API_ENDPOINT
        self.payment_actions = {
            'PINE': self._process_with_banksoft,
            'BRB': self._process_with_brb,
            'DIGIMAIS': self._process_with_white_payment,
        }
        self.contract = contract
        self.benefit_card = benefit_card
        self.contrato_saque = contrato_saque
        self.user = user

    def process_payment(self, client: Cliente, check_commissioning: bool = False):
        if action := self.payment_actions.get(self.payment_provider):
            action(client)
        else:
            raise ValueError(f'Unsupported payment provider: {self.payment_provider}')

        if check_commissioning:
            self._process_commission_if_applicable()

    def _process_commission_if_applicable(self):
        if self.payment_provider in ['PINE', 'DIGIMAIS']:
            parametro_backoffice = ParametrosBackoffice.objects.get(
                tipoProduto=self.contract.tipo_produto
            )
            if parametro_backoffice.enviar_comissionamento:
                self.process_commissioning()

    def process_commissioning(self) -> int:
        return BanksoftAdapter.commissioning(self.contract)

    def update_bank_details(self, account, client, proposal_number=None):
        contrato_saque = self.benefit_card or self.contrato_saque
        if self.payment_provider == 'DIGIMAIS':
            alterar_status(
                self.contract,
                contrato_saque,
                EnumContratoStatus.DIGITACAO,
                ContractStatus.ANDAMENTO_REAPRESENTACAO_DO_PAGAMENTO_DE_SAQUE.value,
            )
            self._process_with_white_payment(client)
        else:
            banksoft_adapter = BanksoftAdapter()
            retorno_banksoft = banksoft_adapter.update_bank_details(
                proposal_number, account, self.contract
            )
            if retorno_banksoft in {200, 201, 202}:
                alterar_status(
                    self.contract,
                    contrato_saque,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.ANDAMENTO_REAPRESENTACAO_DO_PAGAMENTO_DE_SAQUE.value,
                )
            else:
                alterar_status(
                    self.contract,
                    contrato_saque,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                )

    def _process_with_banksoft(self, client: Cliente):
        response = BanksoftAdapter.request_withdrawal(self.contract, client)
        if response in (200, 202):
            if self.benefit_card and (
                self.benefit_card.possui_saque or self.benefit_card.saque_parcelado
            ):
                alterar_status(
                    self.contract,
                    self.benefit_card,
                    EnumContratoStatus.PAGO,
                    ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
                    self.user,
                )
            if self.benefit_card and (
                not self.benefit_card.possui_saque
                and not self.benefit_card.saque_parcelado
            ):
                alterar_status(
                    self.contract,
                    self.benefit_card,
                    EnumContratoStatus.PAGO,
                    ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                    self.user,
                )
            if self.contrato_saque:
                alterar_status(
                    self.contract,
                    self.contrato_saque,
                    EnumContratoStatus.PAGO,
                    ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
                    self.user,
                )

                if self.contrato_saque.saque_parcelado:
                    lancamento_saque_parcelado_fatura(
                        self.contract.id, self.contrato_saque.id
                    )  # Chama sem o argumento retry_count
                else:
                    ajustes_financeiros(
                        self.contract.id, self.contrato_saque.id
                    )  # Chama sem o argumento retry_count
                self.contrato_saque.refresh_from_db()
                self.contrato_saque.data_solicitacao = datetime.now()
                self.contrato_saque.save()
        else:
            if self.benefit_card:
                alterar_status(
                    self.contract,
                    self.benefit_card,
                    EnumContratoStatus.MESA,
                    ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                    self.user,
                )

            elif self.contrato_saque:
                alterar_status(
                    self.contract,
                    self.contrato_saque,
                    EnumContratoStatus.MESA,
                    ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                    self.user,
                )

    def _process_with_brb(self, client: Cliente):
        response = transferencia_saque(client.nu_cpf, self.contract.pk)
        if response in (200, 202):
            retorno_saque.apply_async(args=[self.contract.pk, 0])
            envio_dossie.apply_async(
                args=[
                    self.client.nu_cpf,
                    self.contract.token_contrato,
                    self.benefit_card.possui_saque,
                    self.benefit_card.saque_parcelado,
                ]
            )

    def _process_with_white_payment(self, client: Cliente):
        payment_dto, _ = self._build_payment_dto(client, self.contract)
        access_token = self._get_access_token()
        payment_dict = asdict(payment_dto)
        logger.info({
            'msg': 'Integração white payments',
            'Access_token': access_token,
            'envio white payment': payment_dict,
        })
        access_token = self._get_access_token()
        headers = {'Authorization': f'{access_token}'}
        url = f'{self.base_url}/api/pay'
        response = requests.post(url, json=payment_dict, headers=headers)
        alterar_status(
            self.contract,
            self.benefit_card,
            EnumContratoStatus.ERRO,
            ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value,
        )
        return response.status_code

    @staticmethod
    def _get_access_token():
        url = f'{settings.WHITE_PAYMENTS_API_ENDPOINT}/auth/login'
        credentials = {
            'username': settings.COGNITO_USERNAME,
            'password': settings.COGNITO_PASSWORD,
        }
        try:
            response = requests.post(url, json=credentials)
            response.raise_for_status()
            return response.json().get('access_token')
        except Exception as err:
            logging.exception(f'Failed to get access token from white payments {err}')
            raise

    @staticmethod
    def _build_payment_dto(client: Cliente, contract: Contrato):
        account_details = DadosBancarios.objects.filter(cliente=client).first()
        benefit_card = CartaoBeneficio.objects.get(contrato=contract)
        client_benefit_card = ClienteCartaoBeneficio.objects.filter(
            cliente=client
        ).first()
        ispb = PaymentManager._build_ispb(account_details)
        payment_dto = PaymentRequestDTO(
            id_crontract=int(contract.id),
            cpf=client.nu_cpf,
            branch=account_details.conta_agencia,
            account_number=account_details.conta_numero,
            account_type=account_details.conta_tipo,
            ispb=int(ispb),
            value=float(benefit_card.valor_saque or 0),
            name=client.nome_cliente,
            dock_id=client_benefit_card.id_conta_dock,
        )
        return (payment_dto, benefit_card)

    @staticmethod
    def reprocess_payment_task(webhook_data):
        try:
            contract_id = webhook_data.get('idCrontract')
            contract = Contrato.objects.get(id=contract_id)
            status = webhook_data.get('status')
            client = contract.cliente
            _, benefit_card = PaymentManager._build_payment_dto(client, contract)
            if status == 'REJECTED':
                alterar_status(
                    contract,
                    benefit_card,
                    EnumContratoStatus.ERRO,
                    ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                )
            else:
                account = webhook_data.get('account')
                RetornoSaque.objects.create(
                    contrato=contract,
                    NumeroProposta=webhook_data.get('receiverTaxId'),
                    valorTED=webhook_data.get('value'),
                    Status=webhook_data.get('status'),
                    Banco=webhook_data.get('bank'),
                    Agencia=webhook_data.get('account.branch'),
                    Conta=account.get('account_number'),
                    DVConta=account.get('account_type'),
                    CPFCNPJ=account.get('cpf'),
                    Observacao=account.get('status'),
                )
                if benefit_card.saque_parcelado:
                    lancamento_saque_parcelado_fatura(contract.id, benefit_card.id)
                else:
                    ajustes_financeiros(contract.id, benefit_card.id)

        except Exception:
            alterar_status(
                contract,
                benefit_card,
                EnumContratoStatus.ERRO,
                ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
            )
            logger.info({'msg': 'Falha na execução da reapresentação de pagamento'})
            raise

    @staticmethod
    def _build_ispb(account_details: DadosBancarios) -> str:
        ispb = account_details.conta_banco.split()[0]
        origin_bank = BancosBrasileiros.objects.filter(codigo=ispb).first()
        return origin_bank.ispb
