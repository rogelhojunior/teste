"""This module implements class PayloadBuilder"""

# django imports
from django.conf import settings

# local imports
from contract.models.contratos import Contrato
from core.models import BancosBrasileiros
from handlers.insere_proposta_inss_financeira import separar_numero_ddd
from handlers.insere_proposta_portabilidade_financeira import (
    traduzir_estado_civil,
    traduzir_sexo,
)
from simulacao.communication.hub import definir_data_primeiro_vencimento

from .utils import clear_dots_and_hyphens, fill_zeros_on_right_until_length_equal

# constants
RG_DOCUMENT_TYPES = ('1', 1)
CNH_DOCUMENT_TYPES = ('2', 2)


class PayloadBuilder:
    def __init__(self, contract: Contrato):
        self.contract = contract
        self.client = contract.cliente
        self.portability = contract.get_portability()

    def build(self) -> dict:
        return {
            'NmEndpoint': 'v2/credit_transfer/proposal',
            'NmVerb': 'POST',
            'JsonBody': self.build_json_body(),
        }

    def build_json_body(self) -> dict:
        return {
            'proposal_type': 'inss',
            'purchaser_document_number': settings.CONST_CNPJ_CESSIONARIO,
            'borrower': self.build_borrower(),
            'collaterals': self.build_collaterals(),
            'portability_credit_operation': self.build_portability_credit_operation(),
            'origin_contract': self.build_origin_contract(),
        }

    def build_borrower(self) -> dict:
        return {
            'person_type': 'natural',
            'name': f'{self.client.nome_cliente}',
            'gender': f'{self.build_sex()}',
            'mother_name': f'{self.client.nome_mae}',
            'birth_date': f'{self.client.dt_nascimento}',
            'nationality': f'{self.client.nacionalidade}',
            'marital_status': f'{self.build_marital_status()}',
            'is_pep': False,
            'individual_document_number': f'{clear_dots_and_hyphens(self.client.nu_cpf)}',
            'document_identification_number': f'{self.client.documento_numero}',
            'document_identification_type': f'{self.build_document_type()}',
            'document_identification_date': f'{self.client.documento_data_emissao}',
            'email': f'{self.client.email}',
            'phone': self.build_phone_data(),
            'address': self.build_address_data(),
        }

    def build_sex(self) -> str:
        return f'{traduzir_sexo(self.client.sexo)}'

    def build_marital_status(self) -> str:
        return f'{traduzir_estado_civil(self.client.estado_civil)}'

    def build_document_type(self) -> str:
        document_type = ''
        if self.client.documento_tipo in RG_DOCUMENT_TYPES:
            document_type = 'rg'
        elif self.client.documento_tipo in CNH_DOCUMENT_TYPES:
            document_type = 'cnh'
        return f'{document_type}'

    def build_phone_data(self) -> dict:
        phone_as_str = str(self.client.telefone_celular)
        phone_ddd, phone_number = separar_numero_ddd(phone_as_str)
        return {
            'country_code': '055',
            'area_code': f'{phone_ddd}',
            'number': f'{phone_number}',
        }

    def build_address_data(self) -> dict:
        return {
            'street': f'{self.client.endereco_logradouro}',
            'state': f'{self.client.endereco_uf}',
            'city': f'{self.client.endereco_cidade}',
            'neighborhood': f'{self.client.endereco_bairro}',
            'number': f'{self.client.endereco_numero}',
            'postal_code': f'{clear_dots_and_hyphens(self.client.endereco_cep)}',
            'complement': f'{self.client.endereco_complemento}',
        }

    def build_collaterals(self) -> list:
        return [
            {
                'percentage': 1,
                'collateral_type': 'social_security',
                'collateral_data': {
                    'benefit_number': self.get_benefit(),
                    'state': f'{self.client.endereco_uf}',
                },
            }
        ]

    def get_benefit(self) -> str:
        if self.contract.numero_beneficio:
            return f'{self.contract.numero_beneficio}'
        return ''

    def build_portability_credit_operation(self):
        return {
            'financial': {
                'monthly_interest_rate': self.build_monthly_interest_rate(),
                'number_of_installments': self.build_number_of_installments(),
                'limit_days_to_disburse': 7,
                'first_due_date': self.build_first_due_data(),
            },
            'contract_number': self.build_contract_id(),
        }

    def build_monthly_interest_rate(self) -> float:
        return float(self.portability.taxa / 100) if self.portability.taxa else 0.0

    def build_number_of_installments(self) -> str:
        return int(self.portability.prazo)

    def build_first_due_data(self) -> str:
        first_due_data = definir_data_primeiro_vencimento(self.contract.tipo_produto)
        first_due_data = first_due_data.strftime('%Y-%m-%d')
        return str(first_due_data)

    def build_contract_id(self) -> str:
        contract_id = str(self.contract.id)
        contract_id = fill_zeros_on_right_until_length_equal(10, contract_id)
        contract_id = f'BYX{contract_id}'
        return f'{contract_id}'

    def build_origin_contract(self) -> str:
        return {
            'ispb': self.build_ispb(),
            'contract_number': f'{self.portability.numero_contrato}',
            'last_due_balance': self.build_outstanding_balance(),
        }

    def build_ispb(self) -> str:
        bank_number = self.portability.banco
        numero_conta_banco = bank_number.split()[0]
        if client_bank := BancosBrasileiros.objects.filter(
            codigo=numero_conta_banco
        ).first():
            return f'{client_bank.ispb}'

        return ''

    def build_outstanding_balance(self) -> str:
        return float(self.portability.saldo_devedor)
