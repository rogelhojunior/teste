import logging
from dataclasses import asdict
from decimal import Decimal
from typing import List

import requests
from django.conf import settings
from django.db.models import Case, FloatField, Value, When

from contract.constants import EnumStatus
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.models.convenio import Seguros
from contract.services.insurance.schemas import Endereco, PedidoDeSeguro, Segurado
from contract.services.insurance.tasks import publish_async
from core.models.beneficios_contratado import BeneficiosContratado
from core.models.cliente import Cliente
from handlers.tem_saude import adesao, gerar_token_zeus

logger = logging.getLogger('digitacao')


class InsuranceDataAgent:
    def __init__(self, contract: Contrato = None, client: Cliente = None):
        self.contract = contract
        self.client = client
        self.plan = None
        self.insurance_contract = None
        self.benefits_data = None

    def _set_plan(self, plan):
        self.plan = plan

    def _set_insurance_contract(self, insurance_contract):
        self.insurance_contract = insurance_contract

    @staticmethod
    def get_insurance_by_agreement_and_product(covenant: str, product: int):
        return Seguros.objects.filter(
            convenio=covenant, produto=product, plano__ativo=True
        ).annotate(
            order=Case(
                When(plano__obrigatorio=True, then=Value(0)),
                default=Value(1),
                output_field=FloatField(),
            )
        )

    def calculate_and_sort_insurance_plans(self, insurances: List[Seguros], card_limit):
        insurance_plans_with_value = []

        for insurance in insurances:
            valor_segurado = Decimal(
                f'{insurance.plano.valor_segurado}'.replace('.', '').replace(',', '.')
            )
            if card_limit <= valor_segurado:
                plan_value = self.calculate_plan_value(insurance.plano, card_limit)
                insurance.plano.valor_plano = plan_value
                insurance_plans_with_value.append(insurance.plano)
            else:
                plan_value = self.calculate_plan_value(insurance.plano, valor_segurado)
                insurance.plano.valor_plano = plan_value
                insurance_plans_with_value.append(insurance.plano)

        return sorted(insurance_plans_with_value, key=lambda x: x.valor_plano)

    @staticmethod
    def calculate_plan_value(plano, card_limit):
        if plano.gratuito == 1 or plano.porcentagem_premio is None:
            return Decimal('0.00')
        return (card_limit * plano.porcentagem_premio) / 100

    def save_response_details(self, lucky_number, client_id, apolice):
        try:
            self.insurance_contract.numero_sorte = lucky_number
            self.insurance_contract.save()
            self.create_or_update_benefits_contracted(client_id, apolice)
            logging.info(
                f'Incurance details updated for contract {self.insurance_contract.id}'
            )
            return True

        except Exception as e:
            logging.error(f'Error in update lucky number: {str(e)}')
            return False

    def _contract_external_insurance(self, insurance_dict, client_id):
        url = f'{settings.WHITE_SEGUROS_API_ENDPOINT}/seguros/'
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': settings.SABEMI_SEGUROS_API_KEY,
        }
        try:
            res = publish_async(url, insurance_dict, headers=headers)
            logging.info(
                f'Contract insurance from SABEMI. Status Code: {res.status_code}'
            )
            if res.status_code != 200:
                return {'success': False, 'error': res.text}

            res_json = res.json()
            insurance_details = res_json.get('seguros', [{}])[0]
            lucky_number = insurance_details.get('segurados', [{}])[0].get(
                'numero_sorte'
            )
            apolice = insurance_details.get('apolice')
            self.save_response_details(lucky_number, client_id, apolice)

            logging.info(
                f'Successfully contracted insurance with lucky number: {lucky_number}'
            )

        except requests.RequestException as e:
            return {'success': False, 'error': f'Request failed: {str(e)}'}

        except Exception as e:
            return {
                'success': False,
                'error': f'An unexpected error occurred calling external insurance: {str(e)}',
            }

    def contract_sabemi_insurance(self, plan):
        self._set_insurance_contract(plan)
        self._set_plan(plan.plano)

        address = Endereco(
            endereco=self.client.endereco_logradouro,
            numero=self.client.endereco_numero,
            complemento=self.client.endereco_complemento,
            bairro=self.client.endereco_bairro,
            cidade=self.client.endereco_cidade,
            uf=self.client.endereco_uf,
            cep=self.client.endereco_cep,
        )
        dt_nascimento = self.client.dt_nascimento.isoformat()
        insured_person = Segurado(
            cpf=self.client.nu_cpf_,
            nome=self.client.nome_cliente,
            data_nascimento=dt_nascimento,
            capital=float(self.plan.porcentagem_premio or 0),
            genero=1,
            endereco=address,
            email=self.client.email,
            telefone_celular=self.client.telefone_celular,
            telefone_sms=self.client.telefone_celular,
        )
        start_date = self.contract.criado_em.isoformat()
        insurance_request = PedidoDeSeguro(
            capital=float(self.plan.porcentagem_premio or 0),
            external_id=self.plan.codigo_plano,
            data_inicio_vigencia=start_date,
            frequencia_emissao=self.plan.quantidade_parcelas,
            tipo_vencimento=1,
            dia_vencimento=1,
            segurado=insured_person,
            atividade_principal=0,
            forma_pagamento=5,
        )
        self._contract_external_insurance(
            asdict(insurance_request), self.client.id_unico
        )

    def create_or_update_benefits_contracted(self, client_id, apolice):
        try:
            client = Cliente.objects.get(id_unico=client_id)
            contract = self.insurance_contract.contrato
            client_card = self.contract.cliente_cartao_contrato.get()
            BeneficiosContratado.objects.create(
                id_conta_dock=client_card.id_conta_dock or '',
                id_cartao_dock=client_card.id_registro_dock or '',
                contrato_emprestimo=contract,
                plano=self.plan,
                nome_operadora=self.plan.seguradora.get_nome_display(),
                nome_plano=self.plan.nome,
                obrigatorio=self.plan.obrigatorio,
                identificacao_segurado=apolice,
                valor_plano=self.plan.valor_segurado,
                premio_bruto=float(client_card.limite_pre_aprovado or 0)
                * float(self.plan.porcentagem_premio or 0),
                renovacao_automatica=self.plan.renovacao_automatica,
                cliente=client,
                status=EnumStatus.CRIADO_COM_SUCESSO,
                tipo_plano=self.plan.get_tipo_plano_display(),
            )
            logging.info(
                f'Benefits contracted created for client {client.nome_cliente}'
            )
            return True

        except Cliente.DoesNotExist:
            logging.error(f'Client with id {client_id} not found.')
            return False

    def contract_tem_saude_insurance(self, plan):
        self._set_plan(plan.plano)
        logger.info('Inicio da geração TEM SEGURO')
        token = gerar_token_zeus()
        adesao(self.client, token, self.contract, plan.plano)
        logger.info('Fim da adesao TEM SAUDE')
