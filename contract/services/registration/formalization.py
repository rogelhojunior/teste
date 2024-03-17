import logging

from contract.models.contratos import Contrato
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.services.registration.client import ValidateClientFormalization
from contract.services.signatures.contract_terms import SignFormalizationTerms
from core.models import Cliente
from core.tasks import validar_contrato_assync


class BaseFinalizeFormalization:
    DEFAULT_USER = '00000000099'
    _LOG_MESSAGE = None
    FINALIZATION_TRIGGER_STATUS = None
    STATUS = None

    def __init__(self, client: Cliente, token_envelope: str, geolocation: dict):
        self.client = client
        self.token_envelope = token_envelope

        self.latitude = geolocation['latitude']
        self.longitude = geolocation['longitude']
        self.public_ip = geolocation['public_ip']

    def validate_client(self):
        return ValidateClientFormalization(
            token_envelope=self.token_envelope,
            cpf=self.client.nu_cpf,
        ).validate_contracts()

    def sign_formalization_terms(self):
        return SignFormalizationTerms(
            token_envelope=self.token_envelope,
            latitude=self.latitude,
            longitude=self.longitude,
            public_ip=self.public_ip,
        ).process_products_signature()

    def validate_contract(self):
        validar_contrato_assync.apply_async(
            args=[
                {
                    'token': str(self.token_envelope),
                    'cpf': self.client.nu_cpf,
                },
                str(self.token_envelope),
                self.client.nu_cpf,
                self.DEFAULT_USER,
            ]
        )

    def create_finalization_status(self, status: str, description: str):
        for contract in Contrato.objects.filter(token_envelope=self.token_envelope):
            StatusContrato.objects.create(
                contrato=contract,
                nome=status,
                descricao_mesa=description,
            )

    def log_message(self, message):
        logging.info(
            f'{self.client.id_unico} - Envelope: ({self.token_envelope}) - {message}'
        )

    def finalize_formalization(self):
        self.validate_client()
        self.sign_formalization_terms()
        self.validate_contract()

    def process(
        self,
    ):
        """
        Processa a finalização da formalização.
        """

        self.create_finalization_status(
            status=self.STATUS,
            description=self._LOG_MESSAGE,
        )
        if StatusContrato.objects.filter(
            contrato__token_envelope=self.token_envelope,
            nome=self.FINALIZATION_TRIGGER_STATUS,
        ).exists():
            self.finalize_formalization()
        self.log_message(self._LOG_MESSAGE)


class FinalizeClientFormalizationProcessor(BaseFinalizeFormalization):
    _LOG_MESSAGE = 'Finalizada formalização do cliente'
    FINALIZATION_TRIGGER_STATUS = ContractStatus.FINALIZADA_FORMALIZACAO_ROGADO.value
    STATUS = ContractStatus.FINALIZADA_FORMALIZACAO_CLIENTE.value


class FinalizeRogadoFormalizationProcessor(BaseFinalizeFormalization):
    _LOG_MESSAGE = 'Finalizada formalização do rogado'
    FINALIZATION_TRIGGER_STATUS = ContractStatus.FINALIZADA_FORMALIZACAO_CLIENTE.value
    STATUS = ContractStatus.FINALIZADA_FORMALIZACAO_ROGADO.value
