from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from contract.models.contratos import Contrato, MargemLivre, Portabilidade
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.models import Cliente
from custom_auth.models import Corban
from gestao_comercial.models.representante_comercial import RepresentanteComercial
from simulacao.models import FaixaIdade


class BaseTestContext:
    """
    Class that contains all methods needed for testing creation
    """

    @staticmethod
    def create_client() -> Cliente:
        cliente_data = {
            'tipo_cliente': 1,
            'nome_cliente': 'Nome do Cliente',
            'nu_cpf': '123.456.789-00',
            'dt_nascimento': timezone.localdate() - relativedelta(years=73, months=1),
            'sexo': 'Masculino',
            'estado_civil': 'Solteiro(a)',
            'nome_mae': 'Nome da Mãe do Cliente',
            'nome_pai': 'Nome do Pai do Cliente',
            'documento_tipo': 1,
            'documento_numero': '12345',
            'documento_data_emissao': '2022-01-01',
            'documento_orgao_emissor': 'SSP',
            'documento_uf': 25,
            'naturalidade': 'São Paulo',
            'nacionalidade': 'Brasil',
            'ramo_atividade': 'Tecnologia',
            'tipo_profissao': 'Engenheiro',
            'renda': 5000.00,
            'vr_patrimonio': 100000.00,
            'possui_procurador': False,
            'ppe': False,
            'tipo_logradouro': 'Rua',
            'endereco_residencial_tipo': 1,
            'endereco_logradouro': 'Rua Principal',
            'endereco_numero': '123',
            'endereco_complemento': 'Apto 101',
            'endereco_bairro': 'Bairro Central',
            'endereco_cidade': 'São Paulo',
            'endereco_uf': 25,
            'endereco_cep': '12345-678',
            'tempo_residencia': 'Mais de 5 anos',
            'email': 'cliente@example.com',
            'telefone_celular': '11987654321',
            'telefone_residencial': '1133334444',
            'conjuge_nome': 'Nome do Cônjuge',
            'conjuge_cpf': '987.654.321-00',
            'conjuge_data_nascimento': '1990-02-02',
            'cd_familiar_unico': 'FAM123',
            'form_ed_financeira': True,
            'IP_Cliente': '192.168.1.1',
            'salario_liquido': 6000.00,
        }

        return Cliente.objects.create(**cliente_data)

    @staticmethod
    def create_contract(client: Cliente, bank_correspondent: Corban) -> Contrato:
        """
        Creates the contract

        :param client: Client that owns the contract
        :param bank_correspondent: Bank correspondent to create contract

        :returns: Contrato instance
        """
        data = {
            'id': '1872',
            'tipo_produto': '6',
            'cd_parceiro': None,
            'latitude': None,
            'longitude': None,
            'hash_assinatura': None,
            'ip_publico_assinatura': None,
            'status': '1',
            'token_contrato': '18adc2e5-aee7-491f-a121-9d8af40c1db0',
            'cd_contrato_tipo': '1',
            'taxa': None,
            'taxa_efetiva_ano': '26.38000',
            'taxa_efetiva_mes': '1.97000',
            'vr_tac': None,
            'vr_iof': '6288.15000',
            'vr_iof_adicional': '0.00000',
            'vr_iof_seguro': None,
            'vr_iof_total': None,
            'cet_mes': '2.1600000',
            'cet_ano': '29.2300000',
            'vr_liberado_cliente': '195113.31000',
            'limite_pre_aprovado': None,
            'vencimento_fatura': None,
            'seguro': False,
            'vr_seguro': None,
            'taxa_seguro': None,
            'contrato_assinado': False,
            'contrato_pago': False,
            'cancelada': False,
            'url_formalizacao': None,
            'link_formalizacao_criado_em': None,
            'criado_em': '2023-09-14T22:09:16-03:00',
            'ultima_atualizacao': '2023-09-14T22:12:47-03:00',
            'enviado_documento_pessoal': True,
            'pendente_documento': False,
            'enviado_comprovante_residencia': True,
            'pendente_endereco': False,
            'selfie_enviada': False,
            'selfie_pendente': False,
            'contracheque_enviado': False,
            'contracheque_pendente': False,
            'adicional_enviado': False,
            'adicional_pendente': False,
            'regras_validadas': False,
            'token_envelope': 'c9a38693-d862-4bcb-9dc4-f58726d7a035',
            'dt_pagamento_contrato': None,
            'contrato_digitacao_manual': False,
            'contrato_digitacao_manual_validado': False,
        }

        return Contrato.objects.create(
            **data,
            cliente=client,
            corban=bank_correspondent,
        )

    @staticmethod
    def create_bank_correspondent(
        sales_representative: RepresentanteComercial,
    ) -> Corban:
        """
        Creates the bank correspondent
        """
        data = {
            'corban_name': 'LOJA TESTE',
            'corban_CNPJ': '24.182.961/0001-22',
            'corban_endereco': 'Rua',
            'corban_email': 'teste@byxcapital.com.br',
            'mesa_corban': True,
            'is_active': True,
            'telefone': None,
            'banco': None,
            'agencia': None,
            'conta': None,
            'tipo_estabelecimento': '1',
            'tipo_venda': '1',
            'tipo_cadastro': '1',
            'tipo_relacionamento': '1',
            'loja_matriz': None,
            'nome_representante': 'Teste Corban',
            'nu_cpf_cnpj_representante': '994.160.860-10',
            'telefone_representante': '44959595959',
        }

        return Corban.objects.create(
            **data,
            representante_comercial=sales_representative,
        )

    @staticmethod
    def create_sales_representative():
        """
        Creates the sales representative
        """
        data = {
            'nome': 'Sales Representative Test',
            'nu_cpf_cnpj': '000.000.000-01',
            'telefone': '81999999999',
            'email': 'salesrepresentative@byxcapital.com.br',
            'cargo': '3',
            'tipo_atuacao': '1',
        }

        return RepresentanteComercial.objects.create(**data)

    @staticmethod
    def create_in100_data(client: Cliente) -> DadosIn100:
        """
        Creates in100 data
        """
        data = {
            'id': '535',
            'balance_request_key': '5895ad6c-5693-48c3-aa37-ea0e04b52b27',
            'sucesso_chamada_in100': True,
            'chamada_sem_sucesso': None,
            'sucesso_envio_termo_in100': True,
            'envio_termo_sem_sucesso': '-',
            'in100_data_autorizacao': '2023-09-14T22:07:00-03:00',
            'situacao_beneficio': 'ELEGÍVEIS',
            'cd_beneficio_tipo': '41',
            'uf_beneficio': 'SC',
            'numero_beneficio': '9933',
            'situacao_pensao': 'NÃO PAGADOR',
            'valor_margem': '4320.00',
            'valor_beneficio': '6520.00',
            'valor_liquido': '8274.57',
            'qt_total_emprestimos': None,
            'concessao_judicial': False,
            'possui_representante_legal': None,
            'possui_procurador': False,
            'possui_entidade_representante': False,
            'descricao_recusa': None,
            'ultimo_exame_medico': None,
            'dt_expedicao_beneficio': datetime.strptime('2002-04-14', '%Y-%m-%d'),
            'retornou_IN100': True,
            'tipo_retorno': None,
            'validacao_in100_saldo_retornado': None,
            'validacao_in100_recalculo': None,
        }

        return DadosIn100.objects.create(
            **data,
            cliente=client,
        )

    @staticmethod
    def create_free_margin(contract):
        data = {
            'status': '33',
            'vr_contrato': '38459.54',
            'qtd_parcelas': '8',
            'vr_parcelas': '8000.00',
            'vr_liberado_cliente': '37276.77',
            'ccb_gerada': 'False',
            'fl_seguro': 'False',
            'vr_seguro': '0',
            'dt_vencimento_primeira_parcela': '2023-09-20',
            'dt_vencimento_ultima_parcela': '2023-12-31',
            'vr_tarifa_cadastro': '0',
            'dt_liberado_cliente': '2023-09-20 15:00:00+03:00',
        }
        return MargemLivre.objects.create(**data, contrato=contract)

    @staticmethod
    def create_portability(contract):
        data = {
            'status': '21',
            'banco': '218 - Banco Bonsucesso',
            'numero_beneficio': '992525',
            'especie': '41',
            'numero_contrato': 'mn4514',
            'saldo_devedor': '4000.00',
            'prazo': '80',
            'taxa': '1.8000000',
            'parcela_digitada': '248.00',
            'nova_parcela': '95.53',
            'chave_proposta': '75f3e3c3-9dc0-44ec-96cd-9efececc3651',
            'CPF_dados_divergentes': 'False',
            'related_party_key': 'ebd44766-3fe3-4588-bb89-9f89c7d75bf4',
            'ccb_gerada': 'True',
            'sucesso_insercao_proposta': 'True',
        }
        return Portabilidade.objects.create(**data, contrato=contract)

    @staticmethod
    def create_age_groups():
        age_groups = [
            {
                'nu_idade_minima': 76.0,
                'nu_idade_maxima': 76.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 20000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 48,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 21.0,
                'nu_idade_maxima': 73.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 80000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 84,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 74.0,
                'nu_idade_maxima': 74.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 50000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 72,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 75.0,
                'nu_idade_maxima': 75.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 30000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 60,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 77.0,
                'nu_idade_maxima': 77.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 15000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 36,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 78.0,
                'nu_idade_maxima': 78.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 10000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 24,
                'fl_possui_representante_legal': None,
            },
            {
                'nu_idade_minima': 79.0,
                'nu_idade_maxima': 79.11,
                'vr_minimo': 2000.0,
                'vr_maximo': 5000.0,
                'nu_prazo_minimo': 6,
                'nu_prazo_maximo': 12,
                'fl_possui_representante_legal': None,
            },
        ]
        age_group_models = [
            FaixaIdade(**age_group_data) for age_group_data in age_groups
        ]
        FaixaIdade.objects.bulk_create(
            age_group_models,
        )

    @staticmethod
    def set_client_age(client: Cliente, age: int):
        """
        Updates the dt_nascimento date from Client instance

        :param client: Client instance
        :param age: Age to be calculated.
        """
        client.dt_nascimento = timezone.localdate() - relativedelta(years=age, months=1)
        client.save()

    @staticmethod
    def set_contract_value(free_margin: MargemLivre, contract_value: float):
        """
        Updates the dt_nascimento date from Client instance

        :param free_margin: MargemLivre instance
        :param contract_value: New contract value.
        """
        free_margin.vr_contrato = contract_value
        free_margin.save()
