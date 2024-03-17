"""This module implements class PayloadBuilder"""

# django imports
from django.conf import settings
from django.db.models import Q

# local imports
from contract.models.contratos import Contrato
from core.constants import EnumTipoConta
from core.models import BancosBrasileiros
from core.models.cliente import DadosBancarios
from core.tasks.insert_portability_proposal.utils import (
    clear_dots_and_hyphens,
    fill_zeros_on_right_until_length_equal,
)
from handlers.insere_proposta_inss_financeira import (
    formatar_cpf,
    separar_numero_ddd,
    traduzir_tipo_conta,
)
from handlers.insere_proposta_portabilidade_financeira import (
    traduzir_estado_civil,
    traduzir_sexo,
)
from simulacao.communication.hub import definir_data_primeiro_vencimento

# constants
RG_DOCUMENT_TYPES = ('1', 1)
CNH_DOCUMENT_TYPES = ('2', 2)


class PayloadBuilderPortRefin:
    def __init__(self, contract: Contrato):
        self.contract = contract
        self.client = contract.cliente
        self.portability = contract.get_portability()
        self.refin = contract.get_refin()

    def build_payload_insert_port_refin(self) -> dict:
        return {
            'proposal_type': 'inss',
            'purchaser_document_number': settings.CONST_CNPJ_CESSIONARIO,
            'borrower': self.build_borrower(),
            'collaterals': self.build_collaterals(),
            'portability_credit_operation': self.build_portability_credit_operation(),
            'refinancing_credit_operation': self.build_refinancing_credit_operation(),
            'origin_contract': self.build_origin_contract(),
        }

    def build_borrower(self) -> dict:
        return {
            'person_type': 'natural',
            'name': self.client.nome_cliente,
            'mother_name': self.client.nome_mae,
            'gender': self.build_sex(),
            'birth_date': str(self.client.dt_nascimento),
            'nationality': 'Brasileiro',
            'marital_status': self.build_marital_status(),
            'is_pep': False,
            'individual_document_number': clear_dots_and_hyphens(self.client.nu_cpf),
            'document_identification_number': f'{self.client.documento_numero}',
            'document_identification_type': self.build_document_type(),
            'document_identification_date': str(self.client.documento_data_emissao),
            'phone': self.build_phone_data(),
            'address': self.build_address_data(),
        }

    def build_sex(self) -> str:
        return traduzir_sexo(self.client.sexo)

    def build_marital_status(self) -> str:
        return traduzir_estado_civil(self.client.estado_civil)

    def build_document_type(self) -> str:
        document_type = ''
        if self.client.documento_tipo in RG_DOCUMENT_TYPES:
            document_type = 'rg'
        elif self.client.documento_tipo in CNH_DOCUMENT_TYPES:
            document_type = 'cnh'
        return document_type

    def build_phone_data(self) -> dict:
        phone_as_str = str(self.client.telefone_celular)
        phone_ddd, phone_number = separar_numero_ddd(phone_as_str)
        return {
            'country_code': '055',
            'area_code': phone_ddd,
            'number': phone_number,
        }

    def build_address_data(self):
        return {
            'street': self.client.endereco_logradouro,
            'state': self.client.endereco_uf,
            'city': self.client.endereco_cidade,
            'neighborhood': self.client.endereco_bairro,
            'number': self.client.endereco_numero,
            'postal_code': clear_dots_and_hyphens(self.client.endereco_cep),
            'complement': self.client.endereco_complemento,
        }

    def build_collaterals(self) -> list:
        return [
            {
                'percentage': 1,
                'collateral_type': 'social_security',
                'collateral_data': {
                    'benefit_number': self.get_benefit(),
                    'state': self.client.endereco_uf,
                },
            }
        ]

    def get_benefit(self) -> str:
        return str(self.contract.numero_beneficio)

    def get_customer_bank_details(self):
        dados_bancarios = DadosBancarios.objects.filter(
            cliente=self.contract.cliente,
            retornado_in100=True,
            conta_tipo__in=[
                EnumTipoConta.CORRENTE_PESSOA_FISICA,
                EnumTipoConta.POUPANCA_PESSOA_FISICA,
            ],
        ).exists()
        if dados_bancarios:
            return DadosBancarios.objects.filter(
                Q(cliente=self.contract.cliente)
                & (
                    Q(conta_tipo=EnumTipoConta.CORRENTE_PESSOA_FISICA)
                    | Q(conta_tipo=EnumTipoConta.POUPANCA_PESSOA_FISICA)
                )
                & Q(retornado_in100=True)
            ).last()
        else:
            return DadosBancarios.objects.filter(
                Q(cliente=self.contract.cliente)
                & (
                    Q(conta_tipo=EnumTipoConta.CORRENTE_PESSOA_FISICA)
                    | Q(conta_tipo=EnumTipoConta.POUPANCA_PESSOA_FISICA)
                )
            ).last()

    def build_portability_credit_operation(self):
        return {
            'financial': {
                'installment_face_value': self.build_installment_face_value(
                    'portability'
                ),
                'number_of_installments': self.build_number_of_installments(
                    'portability'
                ),
                'first_due_date': str(self.build_first_due_data()),
            },
            'contract_number': self.build_contract_id('portability'),
        }

    def build_refinancing_credit_operation(self):
        return {
            'financial': {
                'monthly_interest_rate': self.build_monthly_interest_rate(
                    'refinancing'
                ),
                'installment_face_value': self.build_installment_face_value(
                    'refinancing'
                ),
                'number_of_installments': self.build_number_of_installments(
                    'refinancing'
                ),
                'limit_days_to_disburse': 7,
                'first_due_date': str(self.build_first_due_data()),
            },
            'disbursement_bank_account': self.build_disbursement_bank_account(),
            'contract_number': self.build_contract_id('refinancing'),
        }

    def build_disbursement_bank_account(self):
        customer_bank_detail = self.get_customer_bank_details()
        return {
            'name': self.contract.cliente.nome_cliente,
            'account_type': traduzir_tipo_conta(customer_bank_detail.conta_tipo),
            'account_digit': str(customer_bank_detail.conta_digito),
            'account_number': str(customer_bank_detail.conta_numero),
            'branch_number': str(customer_bank_detail.conta_agencia),
            'bank_code': str(customer_bank_detail.conta_banco),
            'ispb': self.build_ispb_client(customer_bank_detail),
            'document_number': formatar_cpf(self.contract.cliente.nu_cpf),
            'transfer_method': 'ted',
        }

    def build_monthly_interest_rate(self, type_operation) -> str:
        if type_operation == 'refinancing':
            return str(self.refin.taxa / 100)
        else:
            return str(self.portability.taxa / 100)

    def build_number_of_installments(self, type_operation) -> str:
        if type_operation == 'refinancing':
            return str(self.refin.prazo)
        else:
            return str(self.portability.prazo)

    def build_installment_face_value(self, type_operation) -> str:
        if type_operation == 'refinancing':
            return str(self.refin.nova_parcela)
        else:
            return str(self.portability.nova_parcela)

    def build_first_due_data(self) -> str:
        first_due_data = definir_data_primeiro_vencimento(self.contract.tipo_produto)
        first_due_data = first_due_data.strftime('%Y-%m-%d')

        return str(first_due_data)

    def build_contract_id(self, type_operation) -> str:
        contract_id = str(self.contract.id)
        contract_id = fill_zeros_on_right_until_length_equal(10, contract_id)
        if type_operation == 'refinancing':
            contract_id = f'BYX9{contract_id}'
        if type_operation == 'portability':
            contract_id = f'BYX{contract_id}'
        return contract_id

    def build_origin_contract(self) -> dict:
        return {
            'ispb': self.build_ispb(),
            'contract_number': self.portability.numero_contrato,
            'last_due_balance': self.build_outstanding_balance(),
        }

    def build_ispb(self) -> str:
        bank_number = self.portability.banco
        numero_conta_banco = bank_number.split()[0]
        origin_bank = BancosBrasileiros.objects.filter(
            codigo=numero_conta_banco
        ).first()
        return origin_bank.ispb

    def build_ispb_client(self, customer_bank_detail) -> str:
        bank_number = customer_bank_detail.conta_banco
        client_bank = BancosBrasileiros.objects.filter(codigo=bank_number).first()
        return str(client_bank.ispb)

    def build_outstanding_balance(self) -> float:
        return float(self.portability.saldo_devedor)
