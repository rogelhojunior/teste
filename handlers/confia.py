import base64
import io
import logging

import boto3
import requests
from django.conf import settings
from requests import ConnectionError, HTTPError, RequestException, Timeout

from custom_auth.models import FeatureToggle

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def publish(mensagem, url):
    try:
        response = requests.post(url, json=mensagem)
        response.raise_for_status()
        return response

    except (requests.HTTPError, ConnectionError, Timeout, RequestException) as err:
        logging.exception(
            msg=f'Error occurred in call {url}: {err}',
            extra={
                'endpoint': url,
                'status_code': response.status_code
                if isinstance(err, HTTPError)
                else None,
                'error_type': type(err).__name__,
            },
        )
        raise
    except Exception:
        logging.exception('Something wrong with request to Face Match')
        raise


def envia_solicitacao_validacao_biometrica(
    selfie_encrypted,
    transactionId,
    auditTrailImage,
    lowQualityAuditTrailImage,
    sessionId,
):
    try:
        mensagem = {
            'facetec': {
                'faceScan': selfie_encrypted,
                'auditTrailImage': auditTrailImage,
                'lowQualityAuditTrailImage': lowQualityAuditTrailImage,
                'sessionId': sessionId,
            }
        }
        url = f'{settings.FACE_MATCH_CONFIA_API_ENDPOINT}/api/send_biometric_data/{transactionId}/'
        response = publish(mensagem, url)

        if response.status_code == 200:
            resposta_servico_externo = response.json()
            return resposta_servico_externo.get('facetec')
        else:
            logging.error(
                f'Falha na requisição: {response.status_code}, {response.text}'
            )
            return {'error': 'Falha na comunicação com o serviço externo'}

    except Exception as e:
        logging.error(f'Erro ao enviar a solicitação de validação biométrica: {e}')
        raise


def enviar_requisicao_criacao_documentos_confia(cliente, anexos_list, token_envelope):
    try:
        confia_payload = {
            'parts': [],
            'type': 'Termos de adesao',
            'documentDescription': 'Formalizacao de contratos',
        }
        dados_cliente = {
            'cpf': cliente.nu_cpf.replace('.', '').replace('-', ''),
            'name': cliente.nome_cliente,
            'phone': cliente.telefone_celular,
            'email': cliente.email,
            'distributionChannels': {
                'sms': False,
                'email': False,
                'whatsapp': False,
            },
        }
        confia_payload['parts'].append(dados_cliente)
        confia_payload['token_envelope'] = token_envelope
        confia_payload['documentos_url'] = anexos_list
        response = enviar_requisicao_formalizacao_externa(confia_payload)
        if response.ok:
            decoded_response = response.json()
            return decoded_response.get('transactionId'), decoded_response.get(
                'message'
            )

    except Exception as e:
        print(f'Exceção capturada durante o envio: {e}')
        return None


def get_facetec_token_session(transaction_id):
    try:
        url = f'{settings.FACE_MATCH_CONFIA_API_ENDPOINT}/api/init_facetec_session/{transaction_id}/'
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    except Exception as e:
        logging.error(f'Erro ao obter token de sessão: {e}')
        raise


def enviar_requisicao_formalizacao_externa(mensagem):
    try:
        logging.info('Enviando contrato para formalizadora externa...')
        url = f'{settings.FACE_MATCH_CONFIA_API_ENDPOINT}/api/sign_document/'
        return publish(mensagem, url)
    except Exception as e:
        logging.error(f'Erro ao enviar contrato para formalizadora externa: {e}')
        return None


def prepare_and_process_document_signature(
    anexo_url,
    transaction_id,
    tipo_anexo,
    latitude,
    longitude,
    altitude='280',
    address='Brasília-DF',
):
    """Processa a assinatura do documento para o CPF especificado."""
    try:
        mensagem = {
            'anexo_url': anexo_url,
            'doc_type': tipo_anexo,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'address': address,
        }

        url = f'{settings.FACE_MATCH_CONFIA_API_ENDPOINT}/api/process_signature/{transaction_id}/'
        resposta = publish(mensagem, url)

        if resposta.status_code == 200:
            return resposta.json()
        logging.error(
            f'Erro ao processar a assinatura do documento: {resposta.status_code}'
        )
        return None

    except Exception as e:
        logging.error(f'Erro ao processar a assinatura do documento: {e}')
        return None


def is_feature_active_for_confia():
    return FeatureToggle.is_feature_active(FeatureToggle.CONFIA_FEATURE)


def get_signed_documents(transaction_id):
    url = f'{settings.FACE_MATCH_CONFIA_API_ENDPOINT}/api/signed_document/{transaction_id}/'
    response = requests.get(url)
    return response.json() if response.ok else None


def download_arquivo_s3_base64(bucket_name, object_key):
    url = s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=31536000,
    )
    response = requests.get(url)
    documento_bytes = response.content
    return io.BytesIO(documento_bytes)


def process_anexo_confia(termos_e_assinaturas_confia, nome_anexo):
    if anexo_confia := next(
        (
            item
            for item in termos_e_assinaturas_confia
            if item['refId'].lower() == nome_anexo.lower()
        ),
        None,
    ):
        try:
            file_content = base64.b64decode(anexo_confia['data'])
            return io.BytesIO(file_content)
        except ValueError:
            pass

    return None


def get_documento_stream_confia_adapter(
    termos_e_assinaturas_confia, bucket_name, object_key, nome_anexo
):
    if isinstance(termos_e_assinaturas_confia, dict):
        return download_arquivo_s3_base64(bucket_name, object_key)

    anexo_stream = process_anexo_confia(termos_e_assinaturas_confia, nome_anexo)
    if anexo_stream is not None:
        return anexo_stream

    return download_arquivo_s3_base64(bucket_name, object_key)


def is_valid_anexo_for_confia(anexo):
    return 'assinado' not in anexo.nome_anexo and 'REGULAMENTO' not in anexo.nome_anexo
