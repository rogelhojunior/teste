import logging
from json import JSONDecodeError
from typing import Union, Optional

import requests
from requests import HTTPError

from api_log.models import LogCliente, QitechRetornos
from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    Portabilidade,
    Refinanciamento,
    MargemLivre,
    Contrato,
)
from handlers.consultas import url_to_base64
from handlers.qitech import QiTech


class UploadQiTechDocument:
    """
    Send an attachment to qitech and persists document_key in product
    """

    _GENERIC_ERROR_MESSAGE = (
        'Erro no envio do documento para a QITECH(validar a extensão do arquivo)'
    )

    def __init__(
        self,
        product: Union[
            Portabilidade,
            Refinanciamento,
            MargemLivre,
        ],
        contract: Contrato,
        attachment: AnexoContrato,
    ):
        self.attachment = attachment
        self.product = product
        self.contract = contract
        self.document_name = self.attachment.nome_anexo
        self.document_url = self.attachment.anexo_url
        self.document_b64 = url_to_base64(self.attachment.anexo_url)
        self.document_extension = (
            'jpg' if self.attachment.anexo_extensao != 'pdf' else 'pdf'
        )
        self.filename = f'{self.document_name}.{self.document_extension}'
        self.mime_type = (
            'application/pdf' if self.document_extension == 'pdf' else 'image/jpeg'
        )

        self.response: Optional[requests.Response] = None
        self.decoded_response: Optional[dict] = None

    def update_product_success_info(self, document_key):
        if self.attachment.tipo_anexo in [
            EnumTipoAnexo.CNH,
            EnumTipoAnexo.DOCUMENTO_FRENTE,
        ]:
            self.save_product_info({
                'sucesso_envio_documento_frente_cnh': True,
                'document_key_QiTech_Frente_ou_CNH': document_key,
            })

        elif self.attachment.tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            self.save_product_info({
                'sucesso_envio_documento_verso': True,
                'document_key_QiTech_Verso': document_key,
            })
        elif self.attachment.tipo_anexo == EnumTipoAnexo.SELFIE:
            self.save_product_info({
                'sucesso_envio_documento_selfie': True,
                'document_key_QiTech_Selfie': document_key,
            })

    def set_response(self):
        qitech = QiTech()
        self.response = qitech.upload_document(
            product=self.product,
            filename=self.filename,
            mime_type=self.mime_type,
            document_url=self.document_url,
            contract=self.contract,
        )
        self.decoded_response = qitech.decode_body(self.response.json())

    def execute(self):
        self.set_response()
        try:
            self.response.raise_for_status()
            self.update_product_success_info(
                document_key=self.decoded_response['document_key']
            )
            self.create_qitech_log(text=self.decoded_response)
        except HTTPError as e:
            self.update_product_error_info(exception=e)
        except JSONDecodeError as e:
            self.process_json_decode_error(
                exception=e,
                response_description=self.response.text,
            )
        except Exception as e:
            self.process_generic_exception(exception=e)

    def update_product_error_info(self, exception: HTTPError):
        if self.attachment.tipo_anexo in [
            EnumTipoAnexo.CNH,
            EnumTipoAnexo.DOCUMENTO_FRENTE,
        ]:
            return self.save_product_info({
                'sucesso_envio_documento_frente_cnh': False,
                'motivo_envio_documento_frente_cnh': self._GENERIC_ERROR_MESSAGE,
            })
        elif self.attachment.tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            return self.save_product_info({
                'sucesso_envio_documento_verso': False,
                'motivo_envio_documento_verso': self._GENERIC_ERROR_MESSAGE,
            })

        elif self.attachment.tipo_anexo == EnumTipoAnexo.SELFIE:
            return self.save_product_info({
                'sucesso_envio_documento_selfie': False,
                'motivo_envio_documento_selfie': self._GENERIC_ERROR_MESSAGE,
            })

    def process_json_decode_error(
        self,
        exception: JSONDecodeError,
        response_description: str,
    ):
        logging.error(
            f'{self.product.chave_proposta} - Contrato ({self.contract.id}): [ENVIO DE DOCUMENTOS] Erro ao decodificar o JSON retornado.',
            extra={
                'error': response_description,
                'exception_description': str(exception),
            },
        )

    def process_generic_exception(self, exception: Exception):
        logging.error(
            f'{self.product.chave_proposta} - Contrato ({self.contract.id}): [ENVIO DE DOCUMENTOS] Erro ao inesperado ao enviar documentos',
            extra={
                'error': str(
                    exception,
                )
            },
        )
        self.create_qitech_log(text={'error': str(exception)})

    def create_qitech_log(self, text: dict):
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=self.contract.cliente)
        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=self.contract.cliente,
            retorno=text,
            tipo='Upload de Documentos',
        )

    def save_product_info(self, product_info: dict):
        for key, value in product_info.items():
            setattr(self.product, key, value)
        self.product.save(update_fields=product_info.keys())


class AttachQiTechDocument:
    def __init__(
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
    ):
        self.product = product
        self.contract = contract
        self.selfie_id = selfie_id
        self.document_identification_id = document_identification_id
        self.document_identification_back_id = document_identification_back_id

        self.response: Optional[requests.Response] = None
        self.decoded_response: Optional[dict] = None

    def set_response(self):
        qi_tech = QiTech()
        self.response = qi_tech.attach_documents(
            product=self.product,
            contract=self.contract,
            selfie_id=self.selfie_id,
            document_identification_id=self.document_identification_id,
            document_identification_back_id=self.document_identification_back_id,
        )
        self.decoded_response = qi_tech.decode_body(self.response.json())

    def log_success(self):
        logging.info(
            f'{self.product.chave_proposta} - Contrato ({self.contract.id}): [VÍNCULO DE DOCUMENTOS] Os documentos foram vinculados com sucesso',
        )

    def log_error(self, exception: Exception):
        logging.info(
            f'{self.product.chave_proposta} - Contrato ({self.contract.id}): [VÍNCULO DE DOCUMENTOS] Houve um erro ao vincular os documentos',
            extra={'error': str(exception)},
        )

    def execute(self) -> tuple[requests.Response, dict]:
        self.set_response()
        try:
            self.response.raise_for_status()
            self.log_success()
        except Exception as e:
            self.log_error(exception=e)

        return self.response, self.decoded_response
