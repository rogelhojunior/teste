"""Tests for the PayloadBuilder class"""

# built-in
import json
from datetime import date, datetime

from django.conf import settings

# third
from django.test import TestCase

# local
from contract.constants import EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.models.bancos_brasileiros import BancosBrasileiros
from core.models.cliente import Cliente
from core.models.parametro_produto import ParametrosProduto
from core.tasks.insert_portability_proposal.PayloadBuilder import PayloadBuilder
from custom_auth.models import Produtos
from handlers.insere_proposta_inss_financeira import separar_numero_ddd
from handlers.insere_proposta_portabilidade_financeira import (
    traduzir_estado_civil,
    traduzir_sexo,
)


class TestPayloadBuilder(TestCase):
    """
    Implements Tests to the class PayloadBuilder.
    """

    def setUp(self):
        # generate a client
        client_data = {
            'tipo_cliente': 1,
            'nome_cliente': 'Teste ',
            'nu_cpf': '027.830.209-20',
            'dt_nascimento': date(1990, 5, 17),
            'documento_data_emissao': date(1998, 6, 4),
        }
        self.client = Cliente.objects.create(**client_data)

        # create bank data
        product_data = {
            'nome': 'Product 1',
            'cd_produto': 'P1',
            'tipo_produto': EnumTipoProduto.FGTS,
            'documento_pessoal': True,
            'comprovante_residencia': True,
            'contracheque': False,
            'ativo': True,
            'confia': False,
        }

        # generate a product
        product = Produtos.objects.create(**product_data)
        bank_data = {
            'codigo': '001',
            'nome': 'Banco do Brasil',
            'ispb': '00000000',
            'aceita_liberacao': True,
        }
        bank = BancosBrasileiros.objects.create(**bank_data)
        bank.produto.add(product)

        # generate a contract
        contract_data = {
            'criado_em': datetime.now(),
            'ultima_atualizacao': datetime.now(),
            'tipo_produto': 6,
            'cliente': self.client,
            'status': 5,
            'cd_contrato_tipo': 4,
            'token_envelope': 'd36317ec-c1e1-4e36-a5e5-1d92266a9fc5',
        }
        self.contract = Contrato.objects.create(**contract_data)

        # generate a portability
        portability_data = {
            'contrato': self.contract,
            'status': 1,
            'banco': f'{bank.codigo} Banco Teste',
            'numero_beneficio': '123456',
            'especie': 'Especie Teste',
            'saldo_devedor': '1000.00',
            'prazo': 12,
            'parcela_digitada': '100.00',
            'nova_parcela': '90.00',
            'CPF_dados_divergentes': False,
            'dt_retorno_dataprev': date(2022, 1, 1),
            'dt_envio_proposta_CIP': date(2022, 1, 2),
            'dt_recebimento_saldo_devedor': date(2022, 1, 3),
            'banco_atacado': 'Banco Atacado Teste',
            'dt_recusa_retido': date(2022, 1, 4),
            'is_proposal_being_inserted': False,
            'taxa': 1.9,
        }
        self.portability = Portabilidade.objects.create(**portability_data)

        # generate a product parameters
        product_parameters_data = {
            'tipoProduto': self.contract.tipo_produto,
            'cet_mes': 1.00,
            'cet_ano': 12.00,
            'valor_tac': 100.00,
            'taxa_minima': 1.00,
            'taxa_maxima': 2.00,
            'valor_minimo_parcela': 100.00,
            'valor_maximo_parcela': 200.00,
            'valor_minimo_emprestimo': 1000.00,
            'valor_maximo_emprestimo': 2000.00,
            'quantidade_minima_parcelas': 1,
            'quantidade_maxima_parcelas': 24,
            'idade_minima': 18,
            'idade_maxima': 65,
            'valor_de_seguranca_proposta': 100.00,
            'dias_limite_para_desembolso': 30,
            'valor_minimo_parcela_simulacao': 100.00,
            'quantidade_dias_uteis_base_simulacao': 5,
            'meses_para_adicionar_quando_dias_uteis_menor_igual_base': 1,
            'meses_para_adicionar_quando_dias_uteis_maior_base': 2,
            'dia_vencimento_padrao_simulacao': 15,
            'valor_liberado_cliente_operacao_min': 1000.00,
            'valor_liberado_cliente_operacao_max': 2000.00,
            'valor_minimo_margem': 100.00,
            'data_inicio_vencimento': 1,
            'prazo_maximo': 24,
            'prazo_minimo': 1,
            'idade_especie_87': 65,
            'aprovar_automatico': False,
            'taxa_proposta_margem_livre': 1.00,
            'multa_contrato_margem_livre': 2.00,
        }
        ParametrosProduto.objects.create(**product_parameters_data)

        # create In100 data
        in100_data = {
            'cliente': self.client,
            'balance_request_key': 'KeyTest',
            'sucesso_chamada_in100': True,
            'chamada_sem_sucesso': 'No error',
            'sucesso_envio_termo_in100': True,
            'envio_termo_sem_sucesso': 'No error',
            'in100_data_autorizacao': datetime.strptime(
                '2022-01-01T00:00:00Z', '%Y-%m-%dT%H:%M:%SZ'
            ),
            'situacao_beneficio': 'Active',
            'cd_beneficio_tipo': 1,
            'uf_beneficio': 'SP',
            'numero_beneficio': '123456',
            'situacao_pensao': 'Active',
            'valor_margem': 1000.00,
            'valor_beneficio': 2000.00,
            'valor_liquido': 1500.00,
            'qt_total_emprestimos': 2,
            'concessao_judicial': False,
            'possui_representante_legal': False,
            'possui_procurador': False,
            'possui_entidade_representante': False,
            'descricao_recusa': 'No refusal',
            'ultimo_exame_medico': date.fromisoformat('2022-01-01'),
            'dt_expedicao_beneficio': date.fromisoformat('2022-01-01'),
            'retornou_IN100': True,
            'tipo_retorno': 'Positive',
            'validacao_in100_saldo_retornado': True,
            'validacao_in100_recalculo': True,
            'vr_disponivel_emprestimo': 500.00,
        }
        DadosIn100.objects.create(**in100_data)

    def build_old_payload(self) -> dict:
        """
        This function builds the payload using the creation old method.
        The function above is a copy of the refactored function that was
        responsible to build the payload.

        OBS: Do not refactor the function bellow.
        """
        contrato = self.contract
        portabilidade = self.portability
        nu_ddd_telefone, nu_telefone = separar_numero_ddd(
            str(contrato.cliente.telefone_celular)
        )
        nu_contrato_financeira = 'BYX' + str(contrato.id).rjust(10, '0')
        tx_efetiva_mes = portabilidade.taxa / 100
        qt_parcelas = portabilidade.prazo
        saldo_devedor_port = portabilidade.saldo_devedor
        cpf = contrato.cliente.nu_cpf
        cpf = cpf.replace('.', '').replace('-', '')
        cep = contrato.cliente.endereco_cep
        cep = cep.replace('-', '')
        cnpj = settings.CONST_CNPJ_CESSIONARIO  # CNPJ do PINE
        cliente = contrato.cliente
        data_nasc = contrato.cliente.dt_nascimento
        data_emissao_doc = contrato.cliente.documento_data_emissao
        estado_civil = traduzir_estado_civil(contrato.cliente.estado_civil)
        sexo = traduzir_sexo(contrato.cliente.sexo)
        numero_banco = portabilidade.banco
        partes = numero_banco.split()
        numero_conta_banco = partes[0]
        banco_do_cliente = BancosBrasileiros.objects.filter(
            codigo=numero_conta_banco
        ).first()
        dados_in100 = DadosIn100.objects.filter(numero_beneficio=contrato.numero_beneficio).first()
        dia_final_vencimento = (
            ParametrosProduto.objects.filter(tipoProduto=contrato.tipo_produto)
            .first()
            .data_inicio_vencimento
        )
        tipo_documento = ''
        if contrato.cliente.documento_tipo in ['2', 2]:
            tipo_documento = 'cnh'
        if contrato.cliente.documento_tipo in ['1', 1]:
            tipo_documento = 'rg'
        return {
            'NmEndpoint': 'v2/credit_transfer/proposal',
            'NmVerb': 'POST',
            'JsonBody': {
                'proposal_type': 'inss',
                'purchaser_document_number': cnpj,
                'borrower': {
                    'person_type': 'natural',
                    'name': f'{contrato.cliente.nome_cliente}',
                    'gender': f'{sexo}',
                    'mother_name': f'{contrato.cliente.nome_mae}',
                    'birth_date': f'{data_nasc}',
                    'nationality': f'{contrato.cliente.nacionalidade}',
                    'marital_status': f'{estado_civil}',
                    'is_pep': False,
                    'individual_document_number': f'{cpf}',
                    'document_identification_number': f'{contrato.cliente.documento_numero}',
                    'document_identification_type': f'{tipo_documento}',
                    'document_identification_date': f'{data_emissao_doc}',
                    'email': f'{contrato.cliente.email}',
                    'phone': {
                        'country_code': '055',
                        'area_code': f'{nu_ddd_telefone}',
                        'number': f'{nu_telefone}',
                    },
                    'address': {
                        'street': f'{contrato.cliente.endereco_logradouro}',
                        'state': f'{contrato.cliente.endereco_uf}',
                        'city': f'{contrato.cliente.endereco_cidade}',
                        'neighborhood': f'{contrato.cliente.endereco_bairro}',
                        'number': f'{contrato.cliente.endereco_numero}',
                        'postal_code': f'{cep}',
                        'complement': f'{contrato.cliente.endereco_complemento}',
                    },
                },
                'collaterals': [
                    {
                        'percentage': 1,
                        'collateral_type': 'social_security',
                        'collateral_data': {
                            'benefit_number': f'{dados_in100.numero_beneficio}',
                            'state': f'{cliente.endereco_uf}',
                        },
                    }
                ],
                'portability_credit_operation': {
                    'financial': {
                        'monthly_interest_rate': float(tx_efetiva_mes),
                        'number_of_installments': int(qt_parcelas),
                        'first_due_date': dia_final_vencimento,
                    },
                    'contract_number': nu_contrato_financeira,
                },
                'origin_contract': {
                    'ispb': f'{banco_do_cliente.ispb}',
                    'contract_number': f'{portabilidade.numero_contrato}',
                    'last_due_balance': float(saldo_devedor_port),
                },
            },
        }

    def test_equal_old(self):
        """
        Test if PayloadBuilder class is building the same payload as the
        old method.
        """
        new_payload = PayloadBuilder(self.contract).build()
        old_payload = self.build_old_payload()
        self.assertEqual(new_payload, old_payload)

    def test_possible_to_generate_json_dumps(self):
        """
        Test if PayloadBuilder class is generating a json.dumps() compatible
        payload.
        """
        payload = PayloadBuilder(self.contract).build()
        try:
            json.dumps(payload)
        except Exception:
            self.assertTrue(False, 'json dumps should not raises an exception.')
