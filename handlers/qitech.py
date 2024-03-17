import locale
import logging
from datetime import datetime
from hashlib import md5
from typing import Union

import requests
from django.conf import settings
from jose import jwt
from requests import Response
from requests_toolbelt import MultipartEncoder

from contract.constants import EnumTipoProduto
from contract.models.contratos import (
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
)
from contract.products.portabilidade_refin.payloads_qitech import (
    PayloadBuilderPortRefin,
)
from core.models import BancosBrasileiros
from core.models.cliente import DadosBancarios
from core.models.parametro_produto import ParametrosProduto
from simulacao.communication.hub import definir_data_primeiro_vencimento
from utils.date import get_valid_disbursement_day

logger = logging.getLogger('digitacao')


class QiTech:
    api_key = settings.QITECH_INTEGRATION_KEY
    client_private_key = settings.QITECH_CLIENT_PRIVATE_KEY
    base_url = settings.QITECH_BASE_ENDPOINT_URL

    endpoints = {
        'endorsement_port_new_credit_correction': f'{base_url}/debt/<proposal_key>/collateral',
        'upload_documents': f'{base_url}/upload',
        'send_debt_documents': f'{base_url}/debt/<proposal_key>/related_party/<related_party_key>/attached_document',
        'send_credit_transfer_documents': f'{base_url}/v2/credit_transfer/proposal/<proposal_key>/related_party/<related_party_key>/attached_document',
        'portability_simulation': f'{base_url}/v2/credit_transfer/proposal_simulation',
        'debt_simulation': f'{base_url}/debt_simulation',
        'debt_cancel': f'{base_url}/debt/<margem_livre_chave_proposta>/cancel_permanently',
        'proposal_simulation': f'{base_url}/v2/credit_transfer/proposal_simulation',
        'accept_refinancing': f'{base_url}/v2/credit_transfer/proposal/<proposal_key>/refinancing_credit_operation/acceptance',
        'cancel_refinancing': f'{base_url}/v2/credit_transfer/proposal/<proposal_key>/refinancing_credit_operation',
        'insert_proposal': f'{base_url}/v2/credit_transfer/proposal',
        'resubmit_payment_refinancing': f'{base_url}/v2/credit_transfer/proposal/<proposal_key>/refinancing_credit_operation',
        'resubmit_payment_free_margin': f'{base_url}/debt/<proposal_key>/change_disbursement_date',
        'proposal_financial_portability': f'{base_url}/v2/credit_transfer/proposal/<proposal_key>',
        'insert_free_margin': f'{base_url}/debt',
    }

    def build_first_due_data(self) -> str:
        first_due_data = definir_data_primeiro_vencimento(
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
        )
        first_due_data = first_due_data.strftime('%Y-%m-%d')
        return str(first_due_data)

    def _get_endpoint(self, url: str) -> str:
        return url.replace(self.base_url, '')

    def _encode_body(self, body: dict) -> dict:
        encoded_body_token = jwt.encode(
            claims=body, key=self.client_private_key, algorithm='ES512'
        )

        return {'encoded_body': encoded_body_token}

    def decode_body(self, response_json: dict) -> dict:
        return (
            jwt.decode(
                token=response_body_encoded,
                key=None,
                options={'verify_signature': False},
            )
            if (response_body_encoded := response_json.get('encoded_body', {}))
            else response_json.get('description')
        )

    def _get_headers(
        self,
        method: str,
        endpoint: str,
        body: bytes,
        content_type='application/json',
    ) -> dict:
        headers = {'alg': 'ES512', 'typ': 'JWT'}

        md5_body = md5(body).hexdigest()

        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

        date = datetime.utcnow().strftime(settings.QITECH_DATE_FORMAT)

        string_to_sign = f'{method}\n{md5_body}\n{content_type}\n{date}\n{endpoint}'

        claims = {'sub': self.api_key, 'signature': string_to_sign}
        encoded_header_token = jwt.encode(
            claims=claims,
            key=self.client_private_key,
            algorithm='ES512',
            headers=headers,
        )

        authorization = f'QIT {self.api_key}:{encoded_header_token}'
        headers = {
            'AUTHORIZATION': authorization,
            'API-CLIENT-KEY': self.api_key,
            'Content-Type': content_type,
        }

        return headers

    def _request(
        self,
        method: str,
        body: dict,
        url: str,
        endpoint: str,
        content_type='application/json',
    ) -> requests.Response:
        request_body = self._encode_body(body)
        encoded_body_token = request_body.get('encoded_body')

        headers = self._get_headers(
            method=method,
            endpoint=endpoint,
            body=encoded_body_token.encode(),
            content_type=content_type,
        )

        response: Response = requests.request(
            method=method, url=url, headers=headers, json=request_body
        )

        if response.status_code not in (200, 201, 202):
            response_body = self.decode_body(response_json=response.json())

            logging.error(f'Ocorreu um erro ao simular o contrato: {response_body}')

        return response

    def debt_simulation(self, body: dict) -> requests.Response:
        method = 'POST'
        resource = 'debt_simulation'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)

        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def debt_cancel(self, body: dict, proposal_key: str) -> requests.Response:
        method = 'POST'
        resource = 'debt_cancel'
        url = self.endpoints.get(resource).replace(
            '<margem_livre_chave_proposta>', proposal_key
        )
        endpoint = self._get_endpoint(url=url)

        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def simulation_port_refin(
        self,
        original_installment_amount: float,
        due_installments_quantity: int,
        monthly_interest: float,
        refin_installment_amount: float,
        refin_installments_quantity: int,
        due_amount: float,
    ) -> requests.Response:
        method = 'POST'
        resource = 'proposal_simulation'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)

        body = {
            'borrower': {'person_type': 'natural'},
            'collaterals': [{'collateral_type': 'social_security'}],
            'portability_credit_operation': {
                'financial': {
                    'installment_face_value': original_installment_amount,
                    'number_of_installments': due_installments_quantity,
                    'first_due_date': str(self.build_first_due_data()),
                }
            },
            'refinancing_credit_operation': {
                'financial': {
                    'monthly_interest_rate': monthly_interest,
                    'installment_face_value': refin_installment_amount,
                    'number_of_installments': refin_installments_quantity,
                    'first_due_date': str(self.build_first_due_data()),
                }
            },
            'origin_contract': {'last_due_balance': due_amount},
        }

        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def simulation_port_refin_v2(
        self,
        original_installment_amount: float,
        due_installments_quantity: int,
        disbursed_amount: float,
        refin_installment_amount: float,
        refin_installments_quantity: int,
        due_amount: float,
    ) -> requests.Response:
        method = 'POST'
        resource = 'proposal_simulation'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)

        body = {
            'borrower': {'person_type': 'natural'},
            'collaterals': [{'collateral_type': 'social_security'}],
            'portability_credit_operation': {
                'financial': {
                    'installment_face_value': original_installment_amount,
                    'number_of_installments': due_installments_quantity,
                    'first_due_date': str(self.build_first_due_data()),
                }
            },
            'refinancing_credit_operation': {
                'financial': {
                    'disbursed_amount': disbursed_amount,
                    'installment_face_value': refin_installment_amount,
                    'number_of_installments': refin_installments_quantity,
                    'first_due_date': str(self.build_first_due_data()),
                }
            },
            'origin_contract': {'last_due_balance': due_amount},
        }

        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def insert_proposal_port_refin(self, contrato):
        method = 'POST'
        resource = 'insert_proposal'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)
        payload = PayloadBuilderPortRefin(contrato)
        body = payload.build_payload_insert_port_refin()
        message = (
            f'{contrato.cliente.id_unico} - Contrato(ID:{contrato.pk}, PORT + REFIN):'
            f' Payload de inserção da proposta '
        )
        logger.info(message, extra={'extra': str(body)})
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def accept_refinancing(self, refinancing: Refinanciamento):
        method = 'POST'
        resource = 'accept_refinancing'
        url = self.endpoints.get(resource).replace(
            '<proposal_key>', refinancing.chave_proposta
        )
        endpoint = self._get_endpoint(url=url)

        installment_face_value = float(refinancing.nova_parcela)
        monthly_interest_rate = round(float(refinancing.taxa), 4)

        # Pega a parcela da portabilidade, caso ela exista e seja menor
        # Utilizando filter.first() para pegar apenas se existir!!
        if portability := Portabilidade.objects.filter(
            contrato=refinancing.contrato
        ).first():
            installment_face_value = float(portability.valor_parcela_original)
            monthly_interest_rate = round(
                float(refinancing.taxa_contrato_recalculada), 4
            )
        product_params = ParametrosProduto.objects.get(
            tipoProduto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
        )

        body = {
            'financial': {
                'monthly_interest_rate': min(
                    monthly_interest_rate, float(product_params.taxa_maxima)
                )
                / 100,
                'installment_face_value': installment_face_value,
                'number_of_installments': refinancing.prazo,
                'disbursement_date': str(get_valid_disbursement_day()),
                'limit_days_to_disburse': 7,
            }
        }
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def accept_refinancing_fixed_disbursed_change(self, refinancing: Refinanciamento):
        """
        Refinancing confirmation with fixed disbursed change amount.


        Args:
            refinancing: Refinanciamento instance

        Returns:

        """
        method = 'POST'
        resource = 'accept_refinancing'
        url = self.endpoints.get(resource).replace(
            '<proposal_key>', refinancing.chave_proposta
        )
        endpoint = self._get_endpoint(url=url)

        portability = Portabilidade.objects.get(contrato=refinancing.contrato)
        body = {
            'financial': {
                'installment_face_value': float(portability.valor_parcela_original),
                'number_of_installments': refinancing.prazo,
                'final_disbursement_amount': float(refinancing.troco_recalculado),
                'disbursement_date': str(get_valid_disbursement_day()),
                'limit_days_to_disburse': 7,
            }
        }
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def cancel_refinancing(self, proposal_key: str):
        method = 'DELETE'
        url = self.endpoints.get('cancel_refinancing').replace(
            '<proposal_key>', proposal_key
        )
        endpoint = self._get_endpoint(url=url)

        return self._request(method=method, body={}, url=url, endpoint=endpoint)

    def payment_resubmission(
        self,
        proposal_key: str,
        disbursement_date: str,
        bank_account: DadosBancarios,
        bank: BancosBrasileiros,
        cpf: str,
        customer_name: str,
        product_type: int = EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
    ) -> requests.Response:
        if product_type == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            resource = 'resubmit_payment_refinancing'
            method = 'PATCH'
            body = {
                'disbursement_date': disbursement_date,
                'disbursement_bank_account': {
                    'account_branch': bank_account.conta_agencia,
                    'account_digit': bank_account.conta_digito,
                    'account_number': bank_account.conta_numero,
                    'bank_code': bank_account.conta_banco,
                    'account_type': 'checking_account',
                    'document_number': cpf,
                    'ispb': bank.ispb,
                    'name': customer_name,
                    'transfer_method': 'ted',
                },
            }
        elif product_type == EnumTipoProduto.MARGEM_LIVRE:
            resource = 'resubmit_payment_free_margin'
            method = 'POST'
            body = {
                'disbursement_date': disbursement_date,
                'disbursement_bank_accounts': [
                    {
                        'branch_number': bank_account.conta_agencia,
                        'account_digit': bank_account.conta_digito,
                        'account_number': bank_account.conta_numero,
                        'account_type': 'checking_account',
                        'document_number': cpf,
                        'bank_code': bank_account.conta_banco,
                        'ispb_number': bank.ispb,
                        'name': customer_name,
                        'percentage_receivable': 100,
                    }
                ],
            }
        else:
            raise NotImplementedError

        url = self.endpoints.get(resource).replace('<proposal_key>', proposal_key)
        endpoint = self._get_endpoint(url=url)

        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def simulation_port_v2_fixed_rate(
        self,
        number_of_installments: int,
        monthly_interest_rate: float,
        due_amount: float,
        first_due_date: str,
    ) -> requests.Response:
        method = 'POST'
        resource = 'portability_simulation'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)

        body = {
            'borrower': {'person_type': 'natural'},
            'collaterals': [{'collateral_type': 'social_security'}],
            'portability_credit_operation': {
                'financial': {
                    'monthly_interest_rate': monthly_interest_rate,
                    'number_of_installments': number_of_installments,
                    'first_due_date': first_due_date,
                }
            },
            'origin_contract': {'last_due_balance': due_amount},
        }

        response = self._request(method=method, body=body, url=url, endpoint=endpoint)
        if response.status_code not in (200, 201, 202):
            logger.info(f'Corpo da requisição de erro : {body}')
        return response

    def simulation_port_v2_fixed_released_value(
        self,
        number_of_installments: int,
        installment_face_value: float,
        due_amount: float,
        first_due_date: str,
    ) -> requests.Response:
        method = 'POST'
        resource = 'portability_simulation'
        url = self.endpoints.get(resource)
        endpoint = self._get_endpoint(url=url)

        body = {
            'borrower': {'person_type': 'natural'},
            'collaterals': [{'collateral_type': 'social_security'}],
            'portability_credit_operation': {
                'financial': {
                    'installment_face_value': installment_face_value,
                    'number_of_installments': number_of_installments,
                    'first_due_date': first_due_date,
                }
            },
            'origin_contract': {'last_due_balance': due_amount},
        }

        response = self._request(method=method, body=body, url=url, endpoint=endpoint)
        if response.status_code not in (200, 201, 202):
            logger.info(f'Corpo da requisição de erro : {body}')
        return response

    def endorsement_correction(
        self,
        contract: Contrato,
        proposal_key: str,
        disbursement_date: str,
        bank_account: DadosBancarios,
        bank: BancosBrasileiros,
        cpf: str,
        customer_name: str,
        type_correction: str,
        request_type: str,
    ) -> requests.Response:
        from handlers.webhook_qitech.enums import PendencyReasonEnum

        if request_type == 'portability' or request_type == 'new_credit':
            resource = 'endorsement_port_new_credit_correction'
            method = 'PATCH'
            if type_correction in (
                PendencyReasonEnum.BANK_DETAILS,
                PendencyReasonEnum.BANK_NUMBER,
            ):
                body = {
                    'disbursement_bank_account': {
                        'bank_code': bank_account.conta_banco,
                        'account_digit': bank_account.conta_digito,
                        'account_branch': bank_account.conta_agencia,
                        'account_number': bank_account.conta_numero,
                        'document_number': cpf,
                    }
                }
            elif type_correction == PendencyReasonEnum.BENEFIT_NUMBER:
                body = {'benefit_number': int(contract.numero_beneficio)}
        elif request_type == 'refinancing':
            method = 'POST'
            resource = 'accept_refinancing'
            body = {
                'disbursement_date': disbursement_date,
                'disbursement_bank_account': {
                    'account_branch': bank_account.conta_agencia,
                    'account_digit': bank_account.conta_digito,
                    'account_number': bank_account.conta_numero,
                    'bank_code': bank_account.conta_banco,
                    'account_type': 'checking_account',
                    'document_number': cpf,
                    'ispb': bank.ispb,
                    'name': customer_name,
                    'transfer_method': 'ted',
                },
            }
        else:
            raise NotImplementedError
        url = self.endpoints.get(resource).replace('<proposal_key>', proposal_key)
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def upload_document(
        self,
        product: Union[
            Portabilidade,
            Refinanciamento,
            MargemLivre,
        ],
        contract: Contrato,
        document_url: str,
        filename: str,
        mime_type: str,
    ) -> requests.Response:
        array_buffer = self.get_document(document_url)
        multipart_data = MultipartEncoder(
            fields={'file': (filename, array_buffer, mime_type)}
        )

        return requests.post(
            self.endpoints.get('upload_documents'),
            headers=self._get_headers(
                method='POST',
                endpoint='/upload',
                body=array_buffer,
                content_type=multipart_data.content_type,
            ),
            data=multipart_data,
        )

    def attach_documents(
        self,
        product: Union[
            Portabilidade,
            Refinanciamento,
            MargemLivre,
        ],
        contract: Contrato,
        selfie_id: str,
        document_identification_id: str,
        document_identification_back_id: str,
    ) -> requests.Response:
        url = (
            self.endpoints.get(self.get_send_documents_resource(contract.tipo_produto))
            .replace('<proposal_key>', product.chave_proposta)
            .replace('<related_party_key>', product.related_party_key)
        )
        body = {
            'selfie': selfie_id,
            'document_identification': document_identification_id,
            'document_identification_back': document_identification_back_id,
        }
        return self._request(
            method='POST', body=body, url=url, endpoint=self._get_endpoint(url)
        )

    @staticmethod
    def get_send_documents_resource(product_type: int) -> str:
        if product_type in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            return 'send_credit_transfer_documents'
        elif product_type == EnumTipoProduto.MARGEM_LIVRE:
            return 'send_debt_documents'
        raise NotImplementedError(f'Produto {product_type} não mapeado')

    @staticmethod
    def get_document(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print(f'Error fetching document: {e}')
            raise

    def refuse_proposal_financial_portability(self, proposal_key):
        method = 'DELETE'
        url = self.endpoints.get('proposal_financial_portability').replace(
            '<proposal_key>', proposal_key
        )
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body={}, url=url, endpoint=endpoint)

    def accept_proposal_financial_portability(self, portability, status):
        method = 'PATCH'
        url = self.endpoints.get('proposal_financial_portability').replace(
            '<proposal_key>', getattr(portability, 'chave_proposta', None)
        )
        body = {
            'status': str(status),
            'financial': {
                'installment_face_value': float(portability.valor_parcela_recalculada)
            },
        }
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def submit_proposal_financial_portability(self, chave_proposta, status):
        method = 'PATCH'
        url = self.endpoints.get('proposal_financial_portability').replace(
            '<proposal_key>', chave_proposta
        )
        body = {
            'status': str(status),
        }
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def insert_free_margin_proposal_financial_portability(self, body):
        method = 'POST'
        url = self.endpoints.get('insert_free_margin')
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body=body, url=url, endpoint=endpoint)

    def insert_proposal_port(self, body):
        method = 'POST'
        url = self.endpoints.get('insert_proposal')
        endpoint = self._get_endpoint(url=url)
        return self._request(method=method, body=body, url=url, endpoint=endpoint)
